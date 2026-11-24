import { build } from "esbuild";
await build({
  entryPoints: ["src/main.tsx"],
  bundle: true,
  minify: true,
  target: ["es2022"],
  outfile: "../src/droidpilot/web/dashboard.js",
  define: { "process.env.NODE_ENV": '"production"' },
  legalComments: "external",
  charset: "utf8",
});
