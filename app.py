from flask import Flask, render_template, request, redirect, url_for, flash
import firebase_admin
from firebase_admin import credentials, firestore
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import parseaddr
from werkzeug.utils import secure_filename
import math
import json
import base64
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import sys

app = Flask(__name__)
app.secret_key = "sinavgram_admin_secret_key"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- GÜVENLİK VE ŞİFRE ÇÖZME ---
BASE64_AES_KEY = "your-base64-aes-key"

def get_decrypted_credentials():
    try:
        key = base64.b64decode(BASE64_AES_KEY)
        aesgcm = AESGCM(key)
        
        with open("config.json", "r") as f:
            data = json.load(f)
            
        nonce_email = base64.b64decode(data["email_nonce"])
        cipher_email = base64.b64decode(data["email_cipher"])
        decrypted_email = aesgcm.decrypt(nonce_email, cipher_email, None).decode('utf-8')
        
        nonce_pass = base64.b64decode(data["pass_nonce"])
        cipher_pass = base64.b64decode(data["pass_cipher"])
        decrypted_pass = aesgcm.decrypt(nonce_pass, cipher_pass, None).decode('utf-8')
        
        return decrypted_email, decrypted_pass
    except FileNotFoundError:
        print("HATA: config.json dosyası bulunamadı.")
        sys.exit(1)
    except Exception as e:
        print(f"HATA: Şifre çözme işlemi başarısız: {str(e)}")
        sys.exit(1)

GMAIL_USER, GMAIL_APP_PASSWORD = get_decrypted_credentials()

FOLDERS = {
    "inbox": "inbox",
    "sent": '"[Gmail]/Sent Mail"',
    "spam": '"[Gmail]/Spam"'
}

def decode_mime_words(s):
    if not s: return ""
    decoded_words = decode_header(s)
    result = []
    for word, encoding in decoded_words:
        if isinstance(word, bytes):
            result.append(word.decode(encoding or 'utf-8', errors='ignore'))
        else:
            result.append(str(word))
    return "".join(result)

def connect_imap(folder_key="inbox"):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    target_folder = FOLDERS.get(folder_key, "inbox")
    mail.select(target_folder)
    return mail

def get_inbox_data(folder_key, page, search_query=""):
    per_page = 20
    mail = connect_imap(folder_key)
    
    try:
        if search_query:
            safe_query = search_query.replace('"', '\\"')
            status, messages = mail.search('UTF-8', 'X-GM-RAW', f'"{safe_query}"')
        else:
            status, messages = mail.search(None, "ALL")
    except Exception as e:
        print(f"Arama Hatası: {e}")
        messages = [b'']
    
    if not messages[0]:
        mail.logout()
        return [], 0

    mail_ids = messages[0].split()
    mail_ids.reverse() 
    
    total_emails = len(mail_ids)
    total_pages = math.ceil(total_emails / per_page)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_mail_ids = mail_ids[start_idx:end_idx]
    
    email_list = []
    for e_id in page_mail_ids:
        res, msg_data = mail.fetch(e_id, '(BODY.PEEK[HEADER])')
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get("Subject", "(Konu Yok)"))
                sender = decode_mime_words(msg.get("From", "(Bilinmeyen Gönderen)"))
                email_list.append({
                    "id": e_id.decode('utf-8'),
                    "subject": subject,
                    "from": sender,
                    "date": msg.get("Date", "")
                })
    mail.logout()
    return email_list, total_pages

# --- FİREBASE BAĞLANTISI ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Firebase başlatılamadı: {e}")


# --- BASİT ÖNBELLEK (CACHE) SİSTEMİ ---
COURSE_CACHE = None
COURSE_CACHE_TIME = 0

def get_cached_courses(db):
    global COURSE_CACHE, COURSE_CACHE_TIME
    if COURSE_CACHE and (time.time() - COURSE_CACHE_TIME) < 3600: # 1 saat cache
        return COURSE_CACHE

    courses_list = []
    course_map = {}
    subtopic_map = {}
    
    try:
        dersler_docs = db.collection('dersler').get()
        for d in dersler_docs:
            d_data = d.to_dict()
            d_name = d_data.get('name', 'Bilinmeyen Ders')
            course_map[d.id] = d_name
            subtopics_list = []
            konular_docs = d.reference.collection('konular').get()
            for k in konular_docs:
                k_data = k.to_dict()
                k_name = k_data.get('name', 'Bilinmeyen Konu')
                subtopic_map[k.id] = k_name
                subtopics_list.append({'id': k.id, 'name': k_name})
            courses_list.append({'id': d.id, 'name': d_name, 'subtopics': subtopics_list})
        
        COURSE_CACHE = (courses_list, course_map, subtopic_map)
        COURSE_CACHE_TIME = time.time()
        return COURSE_CACHE
    except Exception as e:
        print(f"Dersler çekilirken hata: {e}")
        return [], {}, {}


# --- ROUTELER ---
@app.route('/')
def index():
    try:
        page = int(request.args.get('page', 1))
        active_tab = request.args.get('tab', 'pending')
        search_query = request.args.get('q', '') 
        per_page = 30

        # 1. AGGREGATION İLE SIFIR MALİYETLİ SAYIM
        counts = {'pending': 0, 'reported': 0, 'approved': 0}
        try:
            for st in counts.keys():
                aggr_query = db.collection('questions').where('status', '==', st).count()
                aggr_results = aggr_query.get()
                for aggr in aggr_results:
                    counts[st] = aggr[0].value
        except Exception as e:
            print(f"Sayım alınırken hata: {e}")

        # Firebase Değişkenleri
        courses_list, course_map, subtopic_map = get_cached_courses(db)
        paginated_questions = []
        total_pages = 0

        # E-posta Değişkenleri
        email_list = []
        active_mail = None
        current_folder = request.args.get('folder', 'inbox')

        if active_tab in ['pending', 'reported', 'approved', 'newsletter']:
            
            total_items = counts.get(active_tab, 0)
            total_pages = (total_items + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            
            rapor_map = {}
            if active_tab == 'reported':
                raporlar_docs = db.collection('reports').get()
                for r in raporlar_docs:
                    r_data = r.to_dict()
                    qid = r_data.get('questionId') or r_data.get('question_id')
                    if qid:
                        ts = r_data.get('timestamp') or r_data.get('created_at')
                        ts_val = ts.timestamp() if hasattr(ts, 'timestamp') else 0
                        r_date = ts.strftime('%d.%m.%Y %H:%M') if hasattr(ts, 'strftime') else str(ts)
                        reason = r_data.get('reason', r_data.get('report_reason', 'Sebep belirtilmemiş'))
                        if qid in rapor_map:
                            if ts_val > rapor_map[qid]['ts_val']:
                                rapor_map[qid] = {'reason': reason, 'date': r_date, 'ts_val': ts_val}
                        else:
                            rapor_map[qid] = {'reason': reason, 'date': r_date, 'ts_val': ts_val}

            # 2. SADECE İLGİLİ SAYFADAKİ SORULARI ÇEKME
            try:
                questions_query = db.collection('questions')\
                    .where('status', '==', active_tab)\
                    .order_by('created_at', direction=firestore.Query.DESCENDING)\
                    .offset(start_idx)\
                    .limit(per_page)
                
                docs = questions_query.get()
                
                for doc in docs:
                    q_data = doc.to_dict()
                    q_id = doc.id
                    c_id = q_data.get('course_id', '')
                    s_id = q_data.get('subtopic_id', '')
                    q_data['id'] = q_id
                    q_data['course_id'] = c_id
                    q_data['subtopic_id'] = s_id
                    q_data['display_course'] = course_map.get(c_id, f"ID: {c_id}")
                    q_data['display_subtopic'] = subtopic_map.get(s_id, f"ID: {s_id}")
                    
                    if active_tab == 'reported':
                        r_info = rapor_map.get(q_id, {})
                        q_data['report_reason'] = r_info.get('reason', 'Sebep bulunamadı')
                        q_data['report_date'] = r_info.get('date', 'Tarih bulunamadı')
                    
                    paginated_questions.append(q_data)
            except Exception as e:
                print(f"Sorular çekilirken hata: {e}")

        elif active_tab == 'email':
            email_list, email_total_pages = get_inbox_data(current_folder, page, search_query)
            mail_id = request.args.get('mail_id')
            
            if mail_id:
                mail = connect_imap(current_folder)
                res, msg_data = mail.fetch(mail_id.encode('utf-8'), '(RFC822)')
                mail.logout()
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = decode_mime_words(msg.get("Subject", "(Konu Yok)"))
                sender = decode_mime_words(msg.get("From", "(Bilinmeyen Gönderen)"))
                to_addr = decode_mime_words(msg.get("To", ""))
                
                reply_to_email = parseaddr(msg.get("Reply-To") or msg.get("From"))[1]
                reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

                html_body, plain_body = None, None
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        disposition = str(part.get("Content-Disposition"))
                        if content_type in ["text/plain", "text/html"] and "attachment" not in disposition:
                            charset = part.get_content_charset() or 'utf-8'
                            try:
                                payload = part.get_payload(decode=True).decode(charset, errors='replace')
                                if content_type == "text/html": html_body = payload
                                elif content_type == "text/plain": plain_body = payload
                            except: pass
                else:
                    charset = msg.get_content_charset() or 'utf-8'
                    payload = msg.get_payload(decode=True).decode(charset, errors='replace')
                    if msg.get_content_type() == "text/html": html_body = payload
                    else: plain_body = payload

                final_body = html_body if html_body else f"<pre style='white-space: pre-wrap; font-family: inherit;'>{plain_body}</pre>" if plain_body else "<i>(Görüntülenebilir metin içeriği bulunamadı.)</i>"

                active_mail = {
                    "id": mail_id, "subject": subject, "from": sender, "to": to_addr,
                    "date": msg.get("Date", ""), "body": final_body,
                    "reply_to": reply_to_email, "reply_subject": reply_subject
                }
            
            total_pages = email_total_pages 

        return render_template(
            'index.html',
            active_tab=active_tab,
            page=page,
            total_pages=total_pages,
            pending=paginated_questions if active_tab == 'pending' else [],
            reported=paginated_questions if active_tab == 'reported' else [],
            approved=paginated_questions if active_tab == 'approved' else [],
            courses_list=courses_list,
            counts=counts,
            emails=email_list,
            current_folder=current_folder,
            active_mail=active_mail,
            search_query=search_query 
        )
    except Exception as e:
        return f"Sistem Hatası: {str(e)}"


@app.route('/set_status/<qid>/<status>')
def set_status(qid, status):
    try:
        db.document(f"questions/{qid}").update({'status': status})
        flash(f"Soru durumu '{status}' yapıldı.", "success")
    except Exception as e:
        flash(f"Güncelleme Hatası: {e}", "danger")
    return redirect(url_for('index', tab=request.args.get('tab', 'pending')))


@app.route('/update/<qid>', methods=['POST'])
def update_question(qid):
    try:
        data = {
            'text': request.form.get('text'),
            'correct_option': request.form.get('correct_option'),
            'course_id': request.form.get('course_id'),
            'subtopic_id': request.form.get('subtopic_id'),
            'options': {
                'A': request.form.get('option_a'), 'B': request.form.get('option_b'),
                'C': request.form.get('option_c'), 'D': request.form.get('option_d'),
                'E': request.form.get('option_e'),
            }
        }
        image_url = request.form.get('image_url')
        if image_url and image_url.strip():
            data['image_url'] = image_url.strip()
        else:
            data['image_url'] = firestore.DELETE_FIELD
        db.document(f"questions/{qid}").update(data)
        flash("Soru başarıyla güncellendi.", "success")
    except Exception as e:
        flash(f"Güncelleme Hata: {e}", "danger")
    return redirect(url_for('index', tab=request.args.get('tab', 'pending')))


@app.route('/delete/<qid>')
def delete_question(qid):
    try:
        db.document(f"questions/{qid}").delete()
        flash("Soru silindi.", "warning")
    except Exception as e:
        flash(f"Hata: {e}", "danger")
    return redirect(url_for('index', tab=request.args.get('tab', 'pending')))


@app.route('/test_newsletter', methods=['POST'])
def test_newsletter():
    try:
        subject = request.form.get('subject')
        html_content = request.form.get('html_content')
        test_email = "your-personal-mail-address"
        db.collection('mail').document().set({
            'to': test_email,
            'message': {'subject': f"[TEST] {subject}", 'html': html_content}
        })
        flash(f"Test e-postası gönderildi.", "info")
    except Exception as e:
        flash(f"Test gönderimi hatası: {e}", "danger")
    return redirect(url_for('index', tab='newsletter'))


@app.route('/send_newsletter', methods=['POST'])
def send_newsletter():
    try:
        subject = request.form.get('subject')
        html_content = request.form.get('html_content')
        subscribers = db.collection('newsletter_subscribers').get()
        if not subscribers:
            flash("Kayıtlı abone bulunamadı.", "warning")
            return redirect(url_for('index', tab='approved'))
        batch = db.batch()
        for sub in subscribers:
            email_addr = sub.to_dict().get('email')
            if email_addr:
                mail_ref = db.collection('mail').document()
                batch.set(mail_ref, {'to': email_addr, 'message': {'subject': subject, 'html': html_content}})
        batch.commit()
        flash(f"{len(subscribers)} aboneye e-posta gönderim sırasına alındı!", "success")
    except Exception as e:
        flash(f"E-posta hatası: {e}", "danger")
    return redirect(url_for('index', tab='approved'))


@app.route('/archive_season', methods=['POST'])
def archive_season():
    try:
        season_name = request.form.get('season_name')
        if not season_name:
            flash("Geçerli bir sezon adı girin.", "warning")
            return redirect(url_for('index'))
        users_ref = db.collection('users')
        docs = users_ref.stream()
        batch = db.batch()
        count = 0
        total_updated = 0
        for doc in docs:
            data = doc.to_dict()
            current_score = data.get('score', 0)
            batch.update(doc.reference, {'score': 0, f'archived_scores.{season_name}': current_score})
            count += 1
            total_updated += 1
            if count >= 490:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0: batch.commit()
        flash(f"{total_updated} kullanıcının puanı '{season_name}' arşivlendi.", "success")
    except Exception as e:
        flash(f"Sezon güncellenirken hata: {e}", "danger")
    return redirect(url_for('index', tab=request.args.get('tab', 'pending')))


@app.route("/send_email", methods=["POST"])
def send_email():
    to_email = request.form.get("to_email")
    subject = request.form.get("subject")
    html_content = request.form.get("html_content")
    current_folder = request.form.get("current_folder", "inbox")
    files = request.files.getlist("attachments")
    
    try:
        msg = MIMEMultipart("mixed") 
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        
        body_part = MIMEText(html_content, "html")
        msg.attach(body_part)
        
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                msg.attach(part)
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()
        
        flash("E-posta başarıyla gönderildi!", "success")
    except Exception as e:
        flash(f"Gönderim hatası: {str(e)}", "danger")
        
    return redirect(url_for("index", tab='email', folder=current_folder))

if __name__ == '__main__':
    app.run(debug=True, port=5000)