const {
    app,
    BrowserWindow
} = require("electron");

const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

let server = null;
let backendProcess = null;
let collectorProcess = null;
let mainWindow = null;

// Prevent multiple FocusSense Electron instances.
const gotSingleInstanceLock = app.requestSingleInstanceLock();

if (!gotSingleInstanceLock) {
    app.quit();
}

let isQuitting = false;

const FRONTEND_PORT = 4173;
const BACKEND_URL = "http://127.0.0.1:8000";

/* =====================================================
   SHARED DATA DIRECTORY
   ===================================================== */

function getDataDirectory() {
    const dataDirectory = path.join(
        app.getPath("userData"),
        "data"
    );

    try {
        fs.mkdirSync(
            dataDirectory,
            {
                recursive: true
            }
        );
    }
    catch (error) {
        console.error(
            "Could not create data directory:",
            error
        );
    }

    return dataDirectory;
}


/* =====================================================
   CREATE FRONTEND SERVER
   ===================================================== */

function startFrontendServer() {
    return new Promise(
        (resolve, reject) => {

            const distDirectory = path.join(
                __dirname,
                "dist"
            );

            const indexFile = path.join(
                distDirectory,
                "index.html"
            );

            if (!fs.existsSync(distDirectory)) {
                reject(
                    new Error(
                        `Frontend dist folder not found: ${distDirectory}`
                    )
                );

                return;
            }

            if (!fs.existsSync(indexFile)) {
                reject(
                    new Error(
                        `index.html not found: ${indexFile}`
                    )
                );

                return;
            }


            const mimeTypes = {
                ".html": "text/html",
                ".js": "application/javascript",
                ".mjs": "application/javascript",
                ".css": "text/css",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
                ".woff": "font/woff",
                ".woff2": "font/woff2",
                ".ttf": "font/ttf"
            };


            server = http.createServer(
                (request, response) => {

                    try {

                        let requestPath =
                            decodeURIComponent(
                                request.url.split("?")[0]
                            );


                        if (
                            requestPath === "/" ||
                            requestPath === ""
                        ) {
                            requestPath =
                                "/index.html";
                        }


                        const safePath =
                            requestPath.replace(
                                /^[/\\]+/,
                                ""
                            );


                        const requestedFile =
                            path.resolve(
                                distDirectory,
                                safePath
                            );


                        const resolvedDist =
                            path.resolve(
                                distDirectory
                            );


                        if (
                            requestedFile !== resolvedDist &&
                            !requestedFile.startsWith(
                                resolvedDist + path.sep
                            )
                        ) {
                            response.writeHead(403);
                            response.end("Forbidden");
                            return;
                        }


                        fs.readFile(
                            requestedFile,
                            (error, data) => {

                                if (!error) {

                                    const extension =
                                        path.extname(
                                            requestedFile
                                        ).toLowerCase();


                                    const contentType =
                                        mimeTypes[
                                            extension
                                        ] ||
                                        "application/octet-stream";


                                    response.writeHead(
                                        200,
                                        {
                                            "Content-Type":
                                                contentType,

                                            "Cache-Control":
                                                "no-cache"
                                        }
                                    );


                                    response.end(data);

                                    return;
                                }


                                /* SPA FALLBACK */

                                fs.readFile(
                                    indexFile,
                                    (indexError, indexData) => {

                                        if (indexError) {

                                            response.writeHead(500);

                                            response.end(
                                                "Frontend loading error."
                                            );

                                            return;
                                        }


                                        response.writeHead(
                                            200,
                                            {
                                                "Content-Type":
                                                    "text/html",

                                                "Cache-Control":
                                                    "no-cache"
                                            }
                                        );


                                        response.end(indexData);

                                    }
                                );

                            }
                        );

                    }
                    catch (error) {

                        console.error(
                            "Frontend request error:",
                            error
                        );

                        response.writeHead(500);

                        response.end(
                            "Internal frontend server error."
                        );
                    }

                }
            );


            server.once(
                "error",
                (error) => {

                    if (
                        error.code === "EADDRINUSE"
                    ) {

                        console.error(
                            `Frontend port ${FRONTEND_PORT} is already in use.`
                        );

                        reject(error);

                        return;
                    }


                    reject(error);
                }
            );


            server.listen(
                FRONTEND_PORT,
                "127.0.0.1",
                () => {

                    console.log(
                        "--------------------------------"
                    );

                    console.log(
                        "FocusSense Frontend Server Started"
                    );

                    console.log(
                        `Frontend: http://127.0.0.1:${FRONTEND_PORT}`
                    );

                    console.log(
                        `Frontend files: ${distDirectory}`
                    );

                    console.log(
                        "--------------------------------"
                    );

                    resolve();

                }
            );

        }
    );
}


/* =====================================================
   PROCESS HELPERS
   ===================================================== */

function isProcessAlive(child) {
    return !!child && child.exitCode === null && !child.killed;
}

function resolvePackagedResource(...parts) {
    return path.join(process.resourcesPath, ...parts);
}

function resolveDevelopmentBackend() {
    return path.resolve(__dirname, "..", "BackEnd");
}

function findCollectorToken() {
    const candidates = [];

    if (app.isPackaged) {
        candidates.push(
            resolvePackagedResource(
                "backend",
                "FocusSenseCollector",
                "_internal",
                "collector_token.txt"
            ),
            resolvePackagedResource(
                "backend",
                "FocusSenseCollector",
                "collector_token.txt"
            )
        );
    }

    candidates.push(
        path.join(resolveDevelopmentBackend(), "collector_token.txt"),
        path.join(
            resolveDevelopmentBackend(),
            "dist",
            "FocusSenseBackend",
            "_internal",
            "collector_token.txt"
        ),
        path.join(
            resolveDevelopmentBackend(),
            "FocusSense_Package",
            "Collector",
            "collector_token.txt"
        )
    );

    for (const candidate of candidates) {
        try {
            if (fs.existsSync(candidate)) {
                return candidate;
            }
        } catch (_) {}
    }

    return null;
}

function copyCollectorTokenToPackagedCollector() {
    if (!app.isPackaged) {
        return null;
    }

    const target = resolvePackagedResource(
        "backend",
        "FocusSenseCollector",
        "_internal",
        "collector_token.txt"
    );

    if (fs.existsSync(target)) {
        return target;
    }

    const source = findCollectorToken();

    if (!source) {
        console.error("collector_token.txt was not found.");
        return null;
    }

    try {
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.copyFileSync(source, target);
        console.log(`Collector token copied from: ${source}`);
        console.log(`Collector token copied to:   ${target}`);
        return target;
    } catch (error) {
        console.error("Could not copy collector token:", error);
        return null;
    }
}

/* =====================================================
   START BACKEND
   ===================================================== */

function startBackend() {
    const dataDirectory = getDataDirectory();

    const processEnvironment = {
        ...process.env,
        FOCUSSENSE_DATA_DIR: dataDirectory,
        FOCUSSENSE_HOST: "127.0.0.1",
        FOCUSSENSE_PORT: "8000"
    };

    console.log("========================================");
    console.log("Starting FocusSense Backend");
    console.log("========================================");
    console.log(`Data Directory: ${dataDirectory}`);

    if (isProcessAlive(backendProcess)) {
        console.log("Backend is already running.");
        return true;
    }

    let executable;
    let args = [];
    let cwd;

    if (app.isPackaged) {
        executable = resolvePackagedResource(
            "backend",
            "FocusSenseBackend",
            "FocusSenseBackend.exe"
        );
        cwd = path.dirname(executable);
    } else {
        executable = "python.exe";
        args = [
            "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ];
        cwd = resolveDevelopmentBackend();
    }

    console.log(`Backend executable: ${executable}`);
    console.log(`Backend cwd: ${cwd}`);

    if (app.isPackaged && !fs.existsSync(executable)) {
        console.error(`Backend EXE not found: ${executable}`);
        return false;
    }

    try {
        backendProcess = spawn(executable, args, {
            cwd,
            windowsHide: true,
            stdio: ["ignore", "pipe", "pipe"],
            env: processEnvironment
        });
    } catch (error) {
        console.error("Could not start backend:", error);
        backendProcess = null;
        return false;
    }

    backendProcess.stdout?.on("data", data => {
        console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr?.on("data", data => {
        console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.on("error", error => {
        console.error("Backend process error:", error);
    });

    backendProcess.on("exit", (code, signal) => {
        console.log(`Backend stopped. Exit code=${code}, signal=${signal}`);
        backendProcess = null;
    });

    return true;
}

/* =====================================================
   WAIT FOR BACKEND
   ===================================================== */

function waitForBackend(attempts = 60) {
    return new Promise((resolve, reject) => {
        function checkBackend() {
            const request = http.get(
                `${BACKEND_URL}/mongodb-status`,
                response => {
                    response.resume();

                    if (
                        response.statusCode >= 200 &&
                        response.statusCode < 500
                    ) {
                        console.log(
                            `Backend is ready. HTTP ${response.statusCode}`
                        );
                        resolve();
                    } else {
                        retry();
                    }
                }
            );

            request.on("error", retry);

            request.setTimeout(2000, () => {
                request.destroy();
                retry();
            });
        }

        function retry() {
            if (attempts <= 0) {
                reject(new Error("Backend did not start on port 8000."));
                return;
            }

            attempts--;

            console.log(
                `Waiting for backend... attempts left: ${attempts}`
            );

            setTimeout(checkBackend, 1000);
        }

        checkBackend();
    });
}

/* =====================================================
   START COLLECTOR
   ===================================================== */

function startCollector() {
    const dataDirectory = getDataDirectory();

    const processEnvironment = {
        ...process.env,
        FOCUSSENSE_DATA_DIR: dataDirectory,
        FOCUSSENSE_API_URL: BACKEND_URL,
        FOCUSSENSE_COLLECTOR_TIMEOUT: "50",
        FOCUSSENSE_POLL_INTERVAL: "1.0",
        FOCUSSENSE_MIN_ACTIVITY_DURATION: "0.0"
    };

    console.log("========================================");
    console.log("Starting FocusSense Activity Collector");
    console.log("========================================");

    if (isProcessAlive(collectorProcess)) {
        console.log("Collector is already running.");
        return true;
    }

    let executable;
    let args = [];
    let cwd;

    if (app.isPackaged) {
        executable = resolvePackagedResource(
            "backend",
            "FocusSenseCollector",
            "FocusSenseCollector.exe"
        );
        cwd = path.dirname(executable);
    } else {
        executable = "python.exe";
        args = ["activity_collector.py"];
        cwd = resolveDevelopmentBackend();
    }

    console.log(`Collector executable: ${executable}`);
    console.log(`Collector cwd: ${cwd}`);

    if (app.isPackaged && !fs.existsSync(executable)) {
        console.error(`Collector EXE not found: ${executable}`);
        return false;
    }

    // Start the collector even when the user has not logged in yet.
    // FastAPI creates/refreshes collector_token.txt in the shared
    // FOCUSSENSE_DATA_DIR after login, and the collector reads that
    // shared token location when sending activities.
    const tokenPath = copyCollectorTokenToPackagedCollector();

    if (tokenPath) {
        console.log(`Collector token found: ${tokenPath}`);
    } else {
        console.log(
            "Collector token not available yet; collector will wait for login."
        );
    }

    try {
        collectorProcess = spawn(executable, args, {
            cwd,
            windowsHide: true,
            stdio: ["ignore", "pipe", "pipe"],
            env: processEnvironment
        });
    } catch (error) {
        console.error("Could not start collector:", error);
        collectorProcess = null;
        return false;
    }

    collectorProcess.stdout?.on("data", data => {
        console.log(`[Collector] ${data.toString().trim()}`);
    });

    collectorProcess.stderr?.on("data", data => {
        console.log(`[Collector] ${data.toString().trim()}`);
    });

    collectorProcess.on("error", error => {
        console.error("Collector process error:", error);
    });

    collectorProcess.on("exit", (code, signal) => {
        console.log(
            `Collector stopped. Exit code=${code}, signal=${signal}`
        );
        collectorProcess = null;

        if (!isQuitting && code !== 0) {
            console.error(
                "Collector exited unexpectedly. Check the [Collector ERROR] output above."
            );
        }
    });

    console.log("--------------------------------");
    console.log("FocusSense Activity Collector Started");
    console.log("Collector running in background.");
    console.log("--------------------------------");

    return true;
}


/* =====================================================
   CREATE ELECTRON WINDOW
   ===================================================== */

function createWindow() {

    mainWindow =
        new BrowserWindow({

            width: 1400,

            height: 900,

            minWidth: 1000,

            minHeight: 700,

            show: true,

            webPreferences: {

                nodeIntegration:
                    false,

                contextIsolation:
                    true

            }

        });


    mainWindow.loadURL(
        `http://127.0.0.1:${FRONTEND_PORT}`
    );


    mainWindow.webContents.on(
        "did-fail-load",
        (
            event,
            errorCode,
            errorDescription,
            validatedURL
        ) => {

            console.error(
                "Frontend failed to load:"
            );

            console.error(
                "Error Code:",
                errorCode
            );

            console.error(
                "Description:",
                errorDescription
            );

            console.error(
                "URL:",
                validatedURL
            );

        }
    );


    mainWindow.webContents.on(
        "did-finish-load",
        () => {

            console.log(
                "FocusSense frontend loaded successfully."
            );

        }
    );


    mainWindow.webContents.on(
        "render-process-gone",
        (
            event,
            details
        ) => {

            console.error(
                "Electron renderer stopped:"
            );

            console.error(
                details
            );

        }
    );


    mainWindow.on(
        "closed",
        () => {

            mainWindow = null;

        }
    );

}


/* =====================================================
   STOP PROCESS
   ===================================================== */

function stopProcess(processObject, processName) {
    if (!processObject) {
        return;
    }

    try {
        if (process.platform === "win32" && processObject.pid) {
            const killer = spawn(
                "taskkill",
                ["/F", "/T", "/PID", String(processObject.pid)],
                {
                    windowsHide: true,
                    stdio: "ignore"
                }
            );

            killer.on("error", error => {
                console.error(
                    `Could not stop ${processName}:`,
                    error
                );
            });
        } else if (!processObject.killed) {
            processObject.kill();
        }

        console.log(`${processName} stop requested.`);
    } catch (error) {
        console.error(`Error stopping ${processName}:`, error);
    }
}

/* =====================================================
   SINGLE INSTANCE
   ===================================================== */

if (gotSingleInstanceLock) {
    app.on("second-instance", () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) {
                mainWindow.restore();
            }

            mainWindow.focus();
        }
    });
}

/* =====================================================
   APP READY
   ===================================================== */

app.whenReady()
    .then(
        async () => {

            if (!gotSingleInstanceLock) {
                return;
            }

            try {

                console.log(
                    "========================================"
                );

                console.log(
                    "FocusSense Starting"
                );

                console.log(
                    "========================================"

                );
                /* -----------------------------------------
                DATA DIRECTORY
                   ----------------------------------------- */

                const dataDirectory =
                    getDataDirectory();


                console.log(
                    "Data Directory:"
                );

                console.log(
                    dataDirectory
                );


                /* -----------------------------------------
                   1. FRONTEND
                   ----------------------------------------- */

                await startFrontendServer();


                /* -----------------------------------------
                   2. BACKEND
                   ----------------------------------------- */

                const backendStarted =
                    startBackend();


                if (!backendStarted) {

                    throw new Error(
                        "Backend could not be started."
                    );

                }


                /* -----------------------------------------
                   3. WAIT FOR BACKEND
                   ----------------------------------------- */

                await waitForBackend();


                console.log(
                    "Backend is ready."
                );


                /* -----------------------------------------
                   4. COLLECTOR
                   ----------------------------------------- */

                const collectorStarted =
                    startCollector();


                if (!collectorStarted) {

                    throw new Error(
                        "Activity Collector could not be started."
                    );

                }


                /* -----------------------------------------
                   5. ELECTRON WINDOW
                   ----------------------------------------- */

                createWindow();


                console.log(
                    "========================================"
                );

                console.log(
                    "FocusSense startup completed."
                );

                console.log(
                    "Backend: RUNNING"
                );

                console.log(
                    "Collector: RUNNING"
                );

                console.log(
                    "Frontend: RUNNING"
                );

                console.log(
                    "========================================"
                );

            }
            catch (error) {

                console.error(
                    "FocusSense startup error:"
                );

                console.error(
                    error
                );

            }

        }
    );


/* =====================================================
   ACTIVATE
   ===================================================== */

app.on(
    "activate",
    () => {

        if (
            BrowserWindow.getAllWindows()
                .length === 0
        ) {

            createWindow();

        }

    }
);


/* =====================================================
   ALL WINDOWS CLOSED
   ===================================================== */

app.on(
    "window-all-closed",
    () => {

        if (
            process.platform !== "darwin"
        ) {

            app.quit();

        }

    }
);


/* =====================================================
   BEFORE QUIT
   ===================================================== */

app.on(
    "before-quit",
    () => {

        if (isQuitting) {
            return;
        }

        isQuitting = true;

        console.log(
            "Stopping FocusSense..."
        );


        stopProcess(
            collectorProcess,
            "Collector"
        );


        stopProcess(
            backendProcess,
            "Backend"
        );


        if (server) {

            try {

                server.close(
                    () => {

                        console.log(
                            "Frontend server stopped."
                        );

                    }
                );

            }
            catch (error) {

                console.error(
                    "Error stopping frontend server:",
                    error
                );

            }

        }

    }
);