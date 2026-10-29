"""Repair reversible UTF-8-as-CP1252 sequences; preserve other Unicode and URLs."""
import re
_extra='ŒœŠšŸŽžƒˆ˜–—‘’‚“”„†‡•…‰‹›€™'
_continuation='[\u0080-\u00bf'+_extra+']'
_pattern=re.compile('[\u00c2-\u00df]'+_continuation+'|[\u00e0-\u00ef]'+_continuation+'{2}|[\u00f0-\u00f4]'+_continuation+'{3}')
def repair_text(value):
 if not isinstance(value,str):return value
 def decode(match):
  original=match.group()
  try:
   raw=bytes(ord(c) if ord(c)<=255 else c.encode('cp1252')[0] for c in original)
   result=raw.decode('utf-8','strict')
   return original if re.search('[\x00-\x1f\x7f-\x9f\ufffd]',result) else result
  except (UnicodeError,ValueError):return original
 for _ in range(3):
  fixed=_pattern.sub(decode,value)
  if fixed==value:break
  value=fixed
 return value
def repair_tree(value,key=''):
 if key in ('id','performer_id','external_id','source_url','image_url','provider_url','url','front_cover','back_cover','images','source_urls') or key.endswith('_url') or key.endswith('_urls'):return value
 if isinstance(value,dict):return {k:repair_tree(v,k) for k,v in value.items()}
 if isinstance(value,list):return [repair_tree(v,key) for v in value]
 return repair_text(value) if isinstance(value,str) and not value.startswith(('https://','http://')) else value
