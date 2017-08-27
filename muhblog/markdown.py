import re

import flask
import mistune

metadata_regex = re.compile(r'^([a-z]+): (.+)', re.IGNORECASE)


class Renderer(mistune.Renderer):
    spoiler_regex = re.compile(r'\[spoiler\](.+?)\[/spoiler\]', re.DOTALL)
    spoiler_replacement = r'<span class="spoiler">\1</span>'

    def paragraph(self, text):
        subbed = self.spoiler_regex.sub(self.spoiler_replacement, text)
        return super().paragraph(subbed)


def parse_metadata(text):
    split = text.split('\n')
    metadata = {}

    for index, line in enumerate(split):
        if line and not line.isspace():
            if not metadata_regex.search(line):
                return metadata, text
            break

    last_key = last_value = None

    for index, line in enumerate(split[index:]):
        if not line or line.isspace():
            return metadata, '\n'.join(split[index + 1:])
        match = metadata_regex.search(line)
        if match:
            last_key, last_value = match.groups()
            metadata[last_key] = last_value
        else:
            value = line.lstrip()
            if isinstance(last_value, list):
                last_value.append(value)
            else:
                metadata[last_key] = last_value = [last_value, value]


def convert(text):
    parser = mistune.Markdown(renderer=Renderer())
    return flask.Markup(parser(text))
