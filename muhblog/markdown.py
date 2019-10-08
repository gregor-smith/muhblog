import re
from typing import Dict, Tuple, Optional, Union, List

from flask import Markup
from mistune import Markdown, Renderer, escape
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters.html import HtmlFormatter


class SpoilerRenderer(Renderer):
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


def parse_metadata(text: str) -> Tuple[Dict[str, str], str]:
    split = text.split('\n')
    metadata = {}

    regex = re.compile(r'^([a-z]+): (.+)', re.IGNORECASE)

    # text is returned as-is if the first non-whitespace line doesn't match
    # the metadata regex (meaning the file has no metadata)
    for index, line in enumerate(split):
        if line and not line.isspace():
            if regex.search(line) is None:
                return metadata, text
            break

    last_key: Optional[str] = None
    last_value: Optional[Union[str, List[str]]] = None

    for index, line in enumerate(split[index:]):
        if not line or line.isspace():
            # return on the first all whitespace line,
            # as this marks the end of the metadata block
            return metadata, '\n'.join(split[index + 1:])
        match = regex.search(line)
        if match is None:
            value = line.lstrip()
            if isinstance(last_value, list):
                last_value.append(value)
            else:
                metadata[last_key] = last_value = [last_value, value]
        else:
            last_key, last_value = match.groups()
            metadata[last_key] = last_value


def render(text) -> Markup:
    parser = Markdown(renderer=SpoilerRenderer())
    html = parser(text)
    return Markup(html)
