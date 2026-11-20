"""Gmail SMTP transport. Credentials stay in private environment configuration."""
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit

def configuration():
    sender = os.getenv('SENTINEL_MAIL_SENDER','').strip()
    password = os.getenv('SENTINEL_MAIL_APP_PASSWORD','').replace(' ','')
    base = os.getenv('SENTINEL_PUBLIC_URL','').rstrip('/')
    try:
        url = urlsplit(base)
        url.port
    except ValueError:
        url = urlsplit('')
    local = url.hostname in ('127.0.0.1','localhost')
    valid_url = bool(re.fullmatch(r'https?://[^/\s?#@]+/?',base) and url.hostname and not url.username and not url.password and not url.query and not url.fragment and url.path in ('','/') and (url.scheme == 'https' or local and url.scheme == 'http' and os.getenv('SENTINEL_ALLOW_LOCAL_MAIL_LINKS','false').lower()=='true'))
    enabled = os.getenv('SENTINEL_ACCOUNT_EMAIL_ENABLED','false').lower()=='true'
    ready = enabled and valid_url and bool(re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+',sender)) and bool(re.fullmatch(r'[A-Za-z]{16}',password))
    return dict(ready=ready, sender=sender, password=password, base=base, local_only=local)

def status():
    c=configuration()
    return dict(ready=c['ready'], provider='Gmail / Google Workspace', sender=c['sender'] if c['ready'] else '', local_only=c['local_only'], message='Gmail configured for this-computer-only links. Check delivery status after sending.' if c['ready'] and c['local_only'] else 'Gmail configured. Check delivery status after sending to verify the connection.' if c['ready'] else 'Email is not configured. Configure the sender, Google app password and portal URL privately on the server.')

def send_link(recipient, purpose, token):
    c=configuration()
    if not c['ready']: raise RuntimeError('Account email is not configured.')
    message=EmailMessage()
    message['From']=c['sender'];message['To']=recipient
    message['Subject']='Set up your Sentinel account' if purpose=='invite' else 'Reset your Sentinel password'
    minutes=1440 if purpose=='invite' else 30
    link=c['base']+'/#account-link='+token
    message.set_content(('You have been invited to IndustrialAI Sentinel.' if purpose=='invite' else 'A password reset was requested for your IndustrialAI Sentinel account.')+'\n\nOpen this single-use link to choose your password:\n'+link+f'\n\nThis link expires in {minutes} minutes. If you did not expect this email, ignore it. No password has been changed.\nNever share this link.\n')
    with smtplib.SMTP('smtp.gmail.com',587,timeout=15) as smtp:
        smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
        smtp.login(c['sender'],c['password']);smtp.send_message(message)
