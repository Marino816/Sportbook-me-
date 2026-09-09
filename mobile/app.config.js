/**
 * Development-profile overrides only.
 * Production keeps app.json: updates enabled, runtimeVersion appVersion (1.1.0).
 */
module.exports = ({ config }) => {
  const profile = process.env.EAS_BUILD_PROFILE || "";
  const isDevelopmentBuild =
    profile === "development" || process.env.SBME_DEV_CLIENT === "1";
  const plugins = [...(config.plugins || [])];

  if (!isDevelopmentBuild) {
    return config;
  }

  const hasDevClient = plugins.some(
    (plugin) => plugin === "expo-dev-client" || (Array.isArray(plugin) && plugin[0] === "expo-dev-client"),
  );
  if (!hasDevClient) {
    plugins.push("expo-dev-client");
  }

  return {
    ...config,
    plugins,
    runtimeVersion: "1.1.0-dev",
    updates: {
      ...(config.updates || {}),
      enabled: false,
    },
  };
};
