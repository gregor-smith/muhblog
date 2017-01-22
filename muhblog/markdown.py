import re

import mistune

class Renderer(mistune.Renderer):
    spoiler_regex = re.compile(r'\[spoiler\](.+?)\[/spoiler\]', re.DOTALL)
    spoiler_replacement = r'<span class="spoiler">\1</span>'

    def paragraph(self, text):
        subbed = self.spoiler_regex.sub(self.spoiler_replacement, text)
        return super().paragraph(subbed)


def parse_metadata(text):
    split = text.split('\n')
    metadata = {}
    last_key = last_value = None
    for index, line in enumerate(split):
        if not line or line.isspace():
            return metadata, '\n'.join(split[index+1:])
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


def parse(path, metadata=True):
    text = path.read_text(encoding='utf-8')
    if metadata:
        metadata_dict, text = parse_metadata(text)
        return metadata_dict, markdown(text)
    return markdown(text)


metadata_regex = re.compile(r'^([a-z]+): (.+)', re.IGNORECASE)
markdown = mistune.Markdown(renderer=Renderer())