"""Convert provider HTML descriptions to readable plain text without executing markup."""
from html.parser import HTMLParser
import re

class PlainText(HTMLParser):
    blocks={'p','div','section','article','h1','h2','h3','h4','h5','h6','blockquote','ul','ol','li','tr','table','pre'}
    hidden={'script','style','iframe','noscript','template','svg'}
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.suppressed=[]
    def handle_starttag(self,tag,attrs):
        if self.suppressed:
            if tag in self.hidden:self.suppressed.append(tag)
            return
        if tag in self.hidden:self.suppressed.append(tag);return
        if tag in self.blocks:self.parts.append('\n\n')
        elif tag=='br':self.parts.append('\n')
        elif tag in ('td','th'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if self.suppressed:
            if tag==self.suppressed[-1]:self.suppressed.pop()
            return
        if tag in self.blocks:self.parts.append('\n\n')
    def handle_data(self,value):
        if not self.suppressed:self.parts.append(value)


def plain_description(value):
    text=str(value or '')[:100000]
    for _ in range(2):
        parser=PlainText();parser.feed(text);parser.close()
        text=''.join(parser.parts)
        if not re.search(r'</?[a-z][^>]*>',text,re.I):break
    text=text.replace('\xa0',' ')
    text=re.sub(r'[ \t\r\f\v]+',' ',text)
    text='\n'.join(line.strip() for line in text.split('\n'))
    return re.sub(r'\n{3,}','\n\n',text).strip()[:30000]
