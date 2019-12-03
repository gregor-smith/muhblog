import re

from flask import Markup
from mistune import Markdown, Renderer, escape, escape_link
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters.html import HtmlFormatter


class SpoilerRenderer(Renderer):
    def image(self, src: str, title: str, text: str) -> str:
        src = escape_link(src)
        html = f'<img data-lazy-url="{src}"'
        if title:
            title = escape(title, quote=True)
            html = f'{html} title="{title}"'
        if text:
            text = escape(text, quote=True)
            html = f'{html} alt="{text}"'
        return f'{html}/>'

    def paragraph(self, text: str) -> str:
        replaced = re.sub(
            pattern=r'\[spoiler\](.+?)\[/spoiler\]',
            repl=r'<span class="spoiler">\1</span>',
            string=text,
            flags=re.DOTALL
        )
        return super().paragraph(replaced)

    def block_code(self, code: str, lang: str) -> str:
        if not lang:
            return f'<pre><code>{escape(code)}</code></pre>'
        return highlight(
            code=code,
            lexer=get_lexer_by_name(lang, stripall=True),
            formatter=HtmlFormatter(noclasses=True, style='monokai')
        )


def render(text) -> Markup:
    parser = Markdown(renderer=SpoilerRenderer())
    html = parser(text)
    return Markup(html)
