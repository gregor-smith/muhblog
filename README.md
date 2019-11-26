# muhlog

A simple static site generator I use for my blog.

* Looks decent on all devices
* Generates lightweight, minified HTML and CSS.
* Use markdown files for entries
* Has syntax highlighting for code blocks
* Has [spoiler]spoiler tags[/spoiler]

## Usage
Make sure you have `poetry` and `yarn` available.

Install the backend dependencies:
```zsh
$ poetry install
```

Install the frontend dependencies:
```zsh
$ yarn install
```

Write some entries. Entries are markdown (`.md`) files with a special metadata block at the top, as shown below. The date format must be as shown. At least one tag must be present. Subsequent tags must be indented to line up with the first one, as shown.
```
title: Entry title
date: 2018-08-23 19:49
tags: First tag
      Second tag
      Third Tag

The actual text (markdown) goes here.
```
Also write the text that is shown on the 'About' page. This is just a plain markdown file.

Write a config file to `./config.json`. `OUTPUT_DIRECTORY` is where the generated HTML and CSS is stored. By default everything in the directory is deleted beforehand. `OUTPUT_IGNORE` is a list of globs to keep.
```json
{
    "NAME": "my blog",
    "ENTRIES_DIRECTORY": "/home/me/blog/entries",
    "ABOUT_PATH": "/home/me/blog/about.md",
    "OUTPUT_DIRECTORY": "/home/me/blog/freeze",
    "OUTPUT_IGNORE": [
        ".git*",
        "a file.txt",
        "a directory/*"
    ]
}
```

Finally, run the thing:
```zsh
$ yarn freeze
```

## License
MIT
