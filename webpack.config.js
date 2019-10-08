const path = require('path')
const ExtractTextPlugin = require('extract-text-webpack-plugin')

const CSS_FILENAME = 'stylesheet.css'


module.exports = {
    entry: path.join(__dirname, 'muhblog', 'style', 'main.scss'),
    output: {
        path: path.join(__dirname, 'muhblog', 'static'),
        filename: CSS_FILENAME,
    },
    devtool: 'source-map',
    module: {
        rules: [
            {
                test: /\.scss$/,
                use: ExtractTextPlugin.extract({
                    use: [
                        {loader: 'css-loader'},
                        {
                            loader: 'postcss-loader',
                            options: {
                                plugins: () => [
                                    require('precss'),
                                    require('autoprefixer')
                                ]
                            }
                        },
                        {loader: 'sass-loader'}
                    ]
                })
            }
        ]
    },
    plugins: [
        new ExtractTextPlugin(CSS_FILENAME)
    ]
}
