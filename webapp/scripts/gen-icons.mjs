import sharp from "sharp";
import { mkdirSync } from "fs";
mkdirSync("public/icons", { recursive: true });
const src = "public/logo.svg";
await sharp(src).resize(192,192).png().toFile("public/icons/icon-192.png");
await sharp(src).resize(512,512).png().toFile("public/icons/icon-512.png");
await sharp(src).resize(512,512).png().toFile("public/icons/maskable-512.png");
console.log("✅ icons generados en public/icons");
