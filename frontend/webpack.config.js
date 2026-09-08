import path from "node:path";
import { fileURLToPath } from "node:url";

import HtmlWebpackPlugin from "html-webpack-plugin";
import MiniCssExtractPlugin from "mini-css-extract-plugin";
import CssMinimizerPlugin from "css-minimizer-webpack-plugin";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Webpack configuration for the Brocarga Finance Performance Cockpit.
 *
 * Replaces the previous Vite / TanStack Start / Nitro build. The output in
 * `dist/` is a plain static bundle that Django will serve later via
 * `{% static %}` — nothing here assumes a Node.js runtime in production.
 *
 * Babel and PostCSS options are declared inline rather than in separate
 * `babel.config.js` / `postcss.config.js` files. The project is ESM
 * ("type": "module"), and inlining avoids the ESM/CJS config-loading
 * ambiguity those tools have in ESM packages.
 */
export default (_env, argv) => {
  const isProduction = argv.mode === "production";

  return {
    mode: isProduction ? "production" : "development",
    entry: path.resolve(__dirname, "src/index.tsx"),
    devtool: isProduction ? "source-map" : "eval-cheap-module-source-map",

    output: {
      path: path.resolve(__dirname, "dist"),
      // Content hashing lets Django/WhiteNoise cache these forever.
      filename: isProduction ? "assets/[name].[contenthash:8].js" : "assets/[name].js",
      chunkFilename: isProduction
        ? "assets/[name].[contenthash:8].chunk.js"
        : "assets/[name].chunk.js",
      assetModuleFilename: "assets/[name].[hash:8][ext]",
      // Django will serve these under its STATIC_URL. Set PUBLIC_PATH="/static/"
      // (or whatever STATIC_URL ends up being) for the production build so the
      // generated asset URLs resolve. Defaults to "/" for standalone dev.
      publicPath: process.env.PUBLIC_PATH || "/",
      clean: true,
    },

    resolve: {
      extensions: [".tsx", ".ts", ".jsx", ".js"],
      alias: {
        // Mirrors the "@/*" -> "./src/*" mapping in tsconfig.json.
        "@": path.resolve(__dirname, "src"),
      },
    },

    module: {
      rules: [
        {
          test: /\.[jt]sx?$/,
          exclude: /node_modules/,
          use: {
            loader: "babel-loader",
            options: {
              // Do not look for an external babel config file.
              babelrc: false,
              configFile: false,
              cacheDirectory: true,
              presets: [
                ["@babel/preset-env", { bugfixes: true, targets: { esmodules: true } }],
                ["@babel/preset-react", { runtime: "automatic" }],
                ["@babel/preset-typescript", { isTSX: true, allExtensions: true }],
              ],
            },
          },
        },
        {
          test: /\.css$/,
          use: [
            isProduction ? MiniCssExtractPlugin.loader : "style-loader",
            { loader: "css-loader", options: { importLoaders: 1 } },
            {
              loader: "postcss-loader",
              options: {
                postcssOptions: {
                  // Tailwind CSS v4 runs as a PostCSS plugin here. Under Vite it
                  // was the "@tailwindcss/vite" plugin; the CSS in
                  // src/styles.css is unchanged and still uses v4 syntax
                  // (@theme inline, @source, @utility, @custom-variant).
                  plugins: ["@tailwindcss/postcss"],
                },
              },
            },
          ],
        },
        {
          test: /\.(png|jpe?g|gif|svg|webp|avif|woff2?|eot|ttf|otf)$/i,
          type: "asset/resource",
        },
      ],
    },

    plugins: [
      new HtmlWebpackPlugin({
        template: path.resolve(__dirname, "public/index.html"),
        filename: "index.html",
        inject: "body",
        scriptLoading: "defer",
        minify: isProduction && {
          collapseWhitespace: true,
          removeComments: true,
          keepClosingSlash: true,
          removeRedundantAttributes: true,
        },
      }),
      ...(isProduction
        ? [
            new MiniCssExtractPlugin({
              filename: "assets/[name].[contenthash:8].css",
              chunkFilename: "assets/[name].[contenthash:8].chunk.css",
            }),
          ]
        : []),
    ],

    optimization: {
      minimizer: ["...", new CssMinimizerPlugin()],
      splitChunks: {
        cacheGroups: {
          // Recharts + Radix + React are large and change rarely; keeping them
          // in their own chunk keeps the app chunk small across deploys.
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: "vendor",
            chunks: "all",
          },
        },
      },
    },

    performance: {
      // Recharts alone is ~400kb; the default 244kb warning is pure noise here.
      hints: false,
    },

    devServer: {
      port: 8080,
      open: false,
      hot: true,
      historyApiFallback: true,
      client: { overlay: { errors: true, warnings: false } },
      // Deliberately no `static` directory. public/ holds index.html (the
      // HtmlWebpackPlugin template) plus 404.html/500.html, which are reference
      // pages for Django to serve. Exposing public/ here would let the raw,
      // script-less index.html template shadow the generated one and render a
      // blank page.
      static: false,
      // Once the Django backend exists, /api/* is forwarded to it so the
      // browser only ever talks to one origin — matching production, where
      // Django serves both the bundle and the API.
      proxy: [
        {
          context: ["/api"],
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      ],
    },
  };
};
