import click
import flask
import markdown as _markdown

app = flask.Flask(__name__)

def markdown(text):
    return flask.Markup(_markdown.markdown(text))

@app.route('/')
def entry():
    return flask.render_template('entry.html')

@click.command()
@click.option('--host')
@click.option('--port', type=int, default=9001, show_default=True)
@click.option('--debug', is_flag=True, show_default=True)
def main(host, port, debug):
    app.run(host=host, port=port, debug=debug)
