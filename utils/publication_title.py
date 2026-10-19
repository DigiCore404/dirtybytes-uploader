"""Display-only upload titles, independent of torrent payload names."""
def post_title(value):
    if value is None:return ''
    if not isinstance(value,str):raise ValueError('Post title must be text.')
    value=value.strip()
    if len(value)>200 or any(ord(c)<32 or ord(c)==127 or c in '/\\' for c in value):raise ValueError('Use a post title of at most 200 characters, without slashes or control characters.')
    if value in ('.','..'):raise ValueError('Choose a valid post title.')
    return value
