"""Choose uploaded contact-sheet artwork; filenames keep packs deterministic."""

def contact_sheet_artwork(config, uploaded, available=()):
    mode = config.get('MediaTools', 'CONTACT_SHEET_ARTWORK', fallback='none').strip().lower()
    if mode not in ('none', 'backdrop', 'cover', 'both'):
        raise ValueError('Choose none, backdrop, cover or both for contact-sheet artwork.')
    if mode == 'none':return {}
    sheets = sorted(name for name in available if name.lower().endswith('-sheet.jpg'))
    if not sheets:return {}
    url = next((uploaded.get(name) for name in sheets if uploaded.get(name)), None)
    if not url:raise RuntimeError('Contact-sheet artwork was requested, but no generated contact sheet could be uploaded. Publication stopped.')
    return {key:url for key in (('firstpic','backdrop_url') if mode=='both' else ('firstpic',) if mode=='cover' else ('backdrop_url',))}
