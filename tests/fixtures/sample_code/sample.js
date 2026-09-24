/**
 * Sample JavaScript file for testing.
 */
const fs = require("fs");
const path = require("path");

class FileManager {
    constructor(baseDir) {
        this.baseDir = baseDir;
    }

    readFile(fileName) {
        return fs.readFileSync(path.join(this.baseDir, fileName), "utf-8");
    }
}

function calculateSum(a, b) {
    return a + b;
}

module.exports = {
    FileManager,
    calculateSum,
};
