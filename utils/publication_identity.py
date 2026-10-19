"""Resolve the uploader's explicit privacy policy before publishing anything."""
import requests


def resolve_anonymity(config, headers):
    mode=config.get('UploadForm','ANONYMITY',fallback='account').strip().lower()
    if mode=='anonymous':return 1
    if mode=='named':return 0
    if mode!='account':raise ValueError('Choose Account preference, Anonymous or Named in Settings.')
    # Preserve older explicit anonymous configurations until the user saves a mode.
    if config.getint('UploadForm','ANONYMOUS',fallback=0)==1:return 1
    try:
        response=requests.get(config.get('Website','SITEURL').rstrip('/')+'/api/v1/upload-preferences',headers=headers,
                              timeout=15,verify=config.getboolean('Network','VERIFY_SSL',fallback=True),allow_redirects=False)
        response.raise_for_status()
        payload=response.json();user=payload
        value=user.get('anonym')
        if value in ('yes',True,1,'1'):return 1
        if value in ('no',False,0,'0'):return 0
    except (requests.RequestException,ValueError,TypeError,AttributeError):
        pass
    raise ValueError('Could not read your site account anonymity preference. Upload stopped. Choose Anonymous or Named in Settings, or check site API access.')
