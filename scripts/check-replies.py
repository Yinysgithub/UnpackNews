import imaplib
import smtplib
import email
import os
import sys
import json
from email.header import decode_header
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# Load subscriber mapping from config (email -> name)
with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'subscribers.json')) as f:
    KNOWN_SUBSCRIBERS = json.load(f)

MAIL_USER = os.environ['MAIL_USER']
MAIL_PASS = os.environ['MAIL_PASS']
IMAP_HOST = os.environ['IMAP_HOST']
IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
SMTP_HOST = os.environ['SMTP_HOST']
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

def send_notification(subject, body):
    """Send notification email to admin."""
    if not NOTIFY_EMAIL:
        return
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = MAIL_USER
    msg['To'] = NOTIFY_EMAIL
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(MAIL_USER, MAIL_PASS)
        server.send_message(msg)
    print(f'Notification sent to {NOTIFY_EMAIL}')

def decode_str(s):
    """Decode email header string."""
    if s is None:
        return ''
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)

def get_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        return payload.decode(charset, errors='replace')
    return ''

def extract_reply(body):
    """Strip quoted text and signatures to get just the reply."""
    lines = body.strip().split('\n')
    reply_lines = []
    for line in lines:
        # Stop at quoted text markers
        if line.strip().startswith('>'):
            break
        if line.strip().startswith('On ') and 'wrote:' in line:
            break
        if line.strip() == '-- ':
            break
        reply_lines.append(line)
    return '\n'.join(reply_lines).strip()

def load_processed():
    """Load set of already-processed email Message-IDs."""
    path = 'config/.processed-replies.json'
    if os.path.exists(path):
        with open(path) as f:
            return set(json.load(f))
    return set()

def save_processed(processed):
    path = 'config/.processed-replies.json'
    with open(path, 'w') as f:
        json.dump(list(processed), f)

def check_replies():
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(MAIL_USER, MAIL_PASS)
    mail.select('INBOX')

    processed = load_processed()

    # Search for emails from last 7 days (catches read emails too)
    since_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
    status, data = mail.search(None, f'SINCE {since_date}')
    if not data[0]:
        print('No new replies.')
        mail.logout()
        return

    msg_ids = data[0].split()
    found_replies = []

    for msg_id in msg_ids:
        status, msg_data = mail.fetch(msg_id, '(RFC822)')
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        # Skip already-processed emails
        message_id = msg.get('Message-ID', '')
        if message_id in processed:
            continue

        from_addr = email.utils.parseaddr(msg['From'])[1].lower()

        # Skip emails we sent ourselves
        if from_addr == MAIL_USER.lower():
            continue

        subject = decode_str(msg['Subject'])
        date = msg['Date']
        body = get_body(msg)
        reply_text = extract_reply(body)

        if from_addr not in KNOWN_SUBSCRIBERS:
            print(f'\n*** New email from unknown sender: {from_addr} ***')
            print(f'Date: {date}')
            print(f'Subject: {subject}')
            print(f'Message: {reply_text}')
            send_notification(
                f'[Unpack] Unknown sender: {subject}',
                f'From: {from_addr}\nDate: {date}\n\n{reply_text}'
            )
            processed.add(message_id)
            continue

        entry = KNOWN_SUBSCRIBERS[from_addr]
        name = entry['name']
        acct_type = entry.get('type', 'subscriber')

        # Skip test accounts — no logging needed
        if acct_type != 'subscriber':
            print(f'\nTest reply from {from_addr} — skipped (not a real subscriber).')
            processed.add(message_id)
            continue

        found_replies.append({
            'subscriber': name,
            'from': from_addr,
            'subject': subject,
            'date': date,
            'reply': reply_text,
        })
        print(f'\n--- Reply from {name} ---')
        print(f'Date: {date}')
        print(f'Subject: {subject}')
        print(f'Reply: {reply_text}')
        print('---')

        # Append to feedback log
        log_path = f'subscribers/{name}/{name}-feedback-log.md'
        if os.path.exists(log_path):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            with open(log_path, 'a') as f:
                f.write(f'\n---\n\n## Auto-captured — {timestamp}\n\n')
                f.write(f'**Subject:** {subject}\n\n')
                f.write(f'**Raw reply:**\n{reply_text}\n\n')
                f.write('**Integrated into profile:** NOT YET — review needed\n')
            print(f'Logged to {log_path}')
        send_notification(
            f'[Unpack] Reply from {name}: {subject}',
            f'Date: {date}\n\n{reply_text}\n\n— Logged to {name} feedback file. Review needed.'
        )
        processed.add(message_id)

    if not found_replies:
        print('New emails found but none from known subscribers.')

    # Save processed state
    save_processed(processed)
    mail.logout()

if __name__ == '__main__':
    check_replies()
