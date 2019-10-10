const path = require('path')

const ExtractTextPlugin = require('extract-text-webpack-plugin');


const extractPlugin = new ExtractTextPlugin({ filename: 'bundle.css' })


module.exports = {
    entry: path.join(__dirname, 'muhblog', 'scripts', 'index.ts'),
    output: {
        path: path.join(__dirname, 'muhblog', 'static'),
        filename: 'bundle.js'
    },
    module: {
        rules: [
            {
                test: /\.ts$/,
                exclude: '/node_modules/',
                loader: 'ts-loader'
            },
            {
                test: /\.scss$/,
                use: extractPlugin.extract({
                    use: [
                        { loader: 'css-loader' },
                        {
                            loader: 'postcss-loader',
                            options: {
                                plugins: () => [
                                    require('precss'),
                                    require('autoprefixer')
                                ]
                            }
                        },
                        { loader: 'sass-loader' }
                    ]
                })
            }
        ]
    },
    plugins: [
        extractPlugin
    ],
    mode: 'development'
}
