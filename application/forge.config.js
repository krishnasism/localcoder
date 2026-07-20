const { FusesPlugin } = require("@electron-forge/plugin-fuses");
const { FuseV1Options, FuseVersion } = require("@electron/fuses");
const path = require("node:path");

module.exports = {
  packagerConfig: {
    asar: true,
    name: "Localcoder",
    executableName: "Localcoder",
    appBundleId: "com.localcoder.app",
    // Bundled FastAPI binary (built by packaging/build_backend.py)
    extraResource: [path.join(__dirname, "resources", "backend")],
  },
  rebuildConfig: {},
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {
        name: "Localcoder",
        authors: "Krishnasis Mandal",
        description: "Local agentic coding assistant",
        exe: "Localcoder.exe",
        setupExe: "LocalcoderSetup.exe",
      },
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["win32", "darwin", "linux"],
    },
    {
      name: "@electron-forge/maker-dmg",
      config: {
        name: "Localcoder",
        overwrite: true,
      },
    },
    {
      name: "@electron-forge/maker-deb",
      config: {
        options: {
          maintainer: "Krishnasis Mandal",
          homepage: "https://github.com/krishnasism/localcoder",
        },
      },
    },
    {
      name: "@electron-forge/maker-rpm",
      config: {},
    },
  ],
  plugins: [
    {
      name: "@electron-forge/plugin-auto-unpack-natives",
      config: {},
    },
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};
