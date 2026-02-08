const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;

const config = getDefaultConfig(projectRoot);

// Only watch this mobile folder, not parent
config.watchFolders = [projectRoot];

// Exclude parent directories from being watched
config.resolver.blockList = [
  // Ignore parent node_modules
  /\.\.\/node_modules\/.*/,
  /\.\.\/backend\/.*/,
  /\.\.\/frontend\/.*/,
  /\.\.\/dashboard\/.*/,
  /\.\.\/database\/.*/,
  /\.\.\/docs\/.*/,
  /\.\.\/\.github\/.*/,
];

module.exports = config;
