import { readFileSync, writeFileSync } from "node:fs";
import { ApkSigner, SigningKey } from "apk_sign_ts";

const apkPath = process.argv[2];
const outPath = process.argv[3];
const keyDir = process.argv[4];

const apk = new Uint8Array(readFileSync(apkPath));
const privateKey = readFileSync(`${keyDir}/aura.key.pem`, "utf8");
const certificate = readFileSync(`${keyDir}/aura.cert.pem`, "utf8");

const signer = new ApkSigner({
  signingKey: SigningKey.fromPEM(privateKey, certificate),
  digestAlgorithm: "SHA-256",
});

const { signedApk } = await signer.sign(apk);
writeFileSync(outPath, Buffer.from(signedApk));
console.log(`signed ${outPath} (${signedApk.length} bytes)`);
