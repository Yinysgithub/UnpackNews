import smtplib
import sys
import os
import re
from email.mime.text import MIMEText

# Args: subject, body_file, [--to override_email] [--saturday]
subject = sys.argv[1]
body_file = sys.argv[2]

# Parse optional flags
to_email = os.environ.get('RECIPIENT_EMAIL', '')
saturday = False
i = 3
while i < len(sys.argv):
    if sys.argv[i] == '--to' and i + 1 < len(sys.argv):
        to_email = sys.argv[i + 1]
        i += 2
    elif sys.argv[i] == '--saturday':
        saturday = True
        i += 1
    else:
        i += 1

with open(body_file, 'r') as f:
    body = f.read()

# Split body from signature
if 'Have a lovely day' in body:
    parts = body.split('Have a lovely day')
    main_body = parts[0].rstrip()
    sig_text = 'Have a lovely day' + parts[1]
elif 'Thanks for reading' in body:
    parts = body.split('Thanks for reading')
    main_body = parts[0].rstrip()
    sig_text = 'Thanks for reading' + parts[1]
else:
    main_body = body
    sig_text = ''

# Strip standalone dots used as paragraph separators
main_body = re.sub(r'\n\s*\.\s*\n', '\n\n', main_body)

# Convert markdown-style bold to HTML
main_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', main_body)

# Convert markdown links to HTML
main_body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#1a73e8;text-decoration:none;">\1</a>', main_body)

# Convert line breaks to HTML
main_body = main_body.replace('\n\n', '</p><p style="margin:0 0 12px 0;">')
main_body = main_body.replace('\n', '<br>')

# Build signature HTML
if sig_text:
    sig_text = sig_text.strip().replace('\n\n', '<br><br>').replace('\n', '<br>')

# Signature block with standard email delimiter (-- ) so Gmail collapses it as one unit
sig_delimiter = '<div style="margin:24px 0 0 0;">-- </div>'

if saturday:
    signature_html = sig_delimiter + '''<div style="padding-top:8px;border-top:1px solid #e0e0e0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11pt;color:#888;">
<p style="margin:8px 0 0 0;">Thanks for reading this week,<br>Unpack News</p>
<p style="margin:12px 0 0 0;font-size:10pt;">Reply 'unsubscribe' anytime</p>
</div>'''
else:
    sig_lines = sig_text.strip().replace('\n\n', '<br><br>').replace('\n', '<br>') if sig_text else ''
    signature_html = sig_delimiter + f'''<div style="padding-top:8px;border-top:1px solid #e0e0e0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11pt;color:#888;">
<p style="margin:8px 0 0 0;">{sig_lines}</p>
</div>'''

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#ffffff;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#ffffff;">
<tr><td align="center" style="padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;">
<tr><td style="font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:12pt;line-height:1.6;color:#333333;">
<p style="margin:0 0 12px 0;">{main_body}</p>
{signature_html}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

msg = MIMEText(html, 'html', 'utf-8')
msg['Subject'] = subject
msg['From'] = os.environ['MAIL_USER']
msg['To'] = to_email

with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', 587))) as server:
    server.starttls()
    server.login(os.environ['MAIL_USER'], os.environ['MAIL_PASS'])
    server.send_message(msg)

print(f"Sent to {to_email}: {subject}")
