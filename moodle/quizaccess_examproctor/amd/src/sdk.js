(function(global, factory) {
	typeof exports === "object" && typeof module !== "undefined" ? factory(exports) : typeof define === "function" && define.amd ? define(["exports"], factory) : (global = typeof globalThis !== "undefined" ? globalThis : global || self, factory(global.ExamProctorSDK = {}));
})(this, function(exports) {
	Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
	// src/api.ts
	var ApiError = class extends Error {
		constructor(status, code, message) {
			super(message);
			this.status = status;
			this.code = code;
		}
	};
	var SessionApi = class {
		constructor(baseUrl, fetchImpl = (...args) => fetch(...args)) {
			this.baseUrl = baseUrl;
			this.fetchImpl = fetchImpl;
			this.token = "";
			this.sessionId = "";
		}
		async exchange(launchToken) {
			const result = await this.call("POST", "/v1/sessions/exchange", { launch_token: launchToken });
			this.token = result.session_token;
			this.sessionId = result.session_id;
			return result;
		}
		consent(textVersion) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/consent`, {
				text_version: textVersion,
				accepted: true
			});
		}
		precheck(results) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/precheck`, results);
		}
		status() {
			return this.call("GET", `/v1/sessions/${this.sessionId}`);
		}
		presign(body) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/uploads/presign`, body);
		}
		complete(key) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/uploads/complete`, { key });
		}
		events(events) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/events`, { events });
		}
		heartbeat(body) {
			return this.call("POST", `/v1/sessions/${this.sessionId}/heartbeat`, body);
		}
		finish() {
			return this.call("POST", `/v1/sessions/${this.sessionId}/finish`, {});
		}
		/** PUT bytes to a presigned object-store URL. */
		async put(url, data, headers = {}) {
			const response = await this.fetchImpl(url, {
				method: "PUT",
				body: data,
				headers
			});
			if (!response.ok) throw new ApiError(response.status, "put_failed", `object store returned ${response.status}`);
		}
		async call(method, path, body) {
			const headers = { "Content-Type": "application/json" };
			if (this.token) headers.Authorization = `Bearer ${this.token}`;
			const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
				method,
				headers,
				body: body === void 0 ? void 0 : JSON.stringify(body)
			});
			const json = await response.json().catch(() => ({}));
			if (!response.ok) {
				const err = json?.error ?? {};
				throw new ApiError(response.status, err.code ?? "http_error", err.message ?? response.statusText);
			}
			return json;
		}
	};
	// src/capabilities.ts
	var MOBILE_UA = /Android|iPhone|iPad|iPod|Mobile/i;
	function detectCapabilities(env = globalThis) {
		const media = env.navigator?.mediaDevices;
		const ua = env.navigator?.userAgent ?? "";
		const isMobile = MOBILE_UA.test(ua) || /Macintosh/.test(ua) && (env.navigator?.maxTouchPoints ?? 0) > 1;
		return {
			camera: typeof media?.getUserMedia === "function",
			screen: !isMobile && typeof media?.getDisplayMedia === "function",
			indexedDb: env.indexedDB !== void 0,
			isMobile
		};
	}
	// src/devices.ts
	function classify(error) {
		const name = error?.name ?? "";
		if (name === "NotAllowedError" || name === "SecurityError") return "denied";
		if (name === "NotFoundError" || name === "OverconstrainedError") return "missing";
		return "missing";
	}
	async function checkCamera(media) {
		if (!media?.getUserMedia) return { status: "unsupported" };
		try {
			return {
				status: "ok",
				stream: await media.getUserMedia({
					video: {
						width: 640,
						height: 480
					},
					audio: false
				})
			};
		} catch (error) {
			return { status: classify(error) };
		}
	}
	async function checkScreen(media, isMobile) {
		if (isMobile || !media?.getDisplayMedia) return { status: "unsupported" };
		try {
			const stream = await media.getDisplayMedia({
				video: { displaySurface: "monitor" },
				audio: false
			});
			return {
				status: "ok",
				stream,
				surface: stream.getVideoTracks()[0]?.getSettings().displaySurface ?? null
			};
		} catch (error) {
			return { status: classify(error) };
		}
	}
	function stopStream(stream) {
		stream?.getTracks().forEach((track) => track.stop());
	}
	// src/precheck.ts
	var PrecheckController = class {
		constructor(deps) {
			this.deps = deps;
			this.camera = { status: "not_requested" };
			this.screen = { status: "not_requested" };
		}
		async start(launchToken) {
			this.session = await this.deps.api.exchange(launchToken);
			return this.session;
		}
		get policy() {
			if (!this.session) throw new Error("start() first");
			return this.session.policy;
		}
		async consent() {
			if (!this.session) throw new Error("start() first");
			await this.deps.api.consent(this.session.consent_text_version);
		}
		async requestCamera() {
			stopStream(this.camera.stream);
			this.camera = await checkCamera(this.deps.media);
			return this.camera;
		}
		async requestScreen() {
			stopStream(this.screen.stream);
			this.screen = await checkScreen(this.deps.media, this.deps.caps.isMobile);
			return this.screen;
		}
		/** Devices the policy needs that have not been tried yet. */
		pendingDevices() {
			const pending = [];
			if (this.policy.camera && this.camera.status === "not_requested") pending.push("camera");
			if (this.policy.screen && this.screen.status === "not_requested" && !this.deps.caps.isMobile) pending.push("screen");
			return pending;
		}
		results() {
			const screen = this.policy.screen && this.deps.caps.isMobile && this.screen.status === "not_requested" ? "unsupported" : this.screen.status;
			return {
				camera: this.camera.status,
				screen,
				screen_surface: this.screen.surface ?? null,
				network_ok: true
			};
		}
		/** Ask the service to decide, then wait until it has told Moodle. Streams stay open for capture. */
		async submit() {
			let status = await this.deps.api.precheck(this.results());
			if (status.status === "blocked") return {
				kind: "blocked",
				reasons: status.reasons
			};
			const sleep = this.deps.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
			const interval = this.deps.pollIntervalMs ?? 2e3;
			let waited = 0;
			while (!status.ready_delivered) {
				if (waited >= (this.deps.pollTimeoutMs ?? 6e4)) return { kind: "timeout" };
				await sleep(interval);
				waited += interval;
				status = await this.deps.api.status();
			}
			return { kind: "ready" };
		}
	};
	// src/capture.ts
	async function sha256Hex(data) {
		const digest = await crypto.subtle.digest("SHA-256", data);
		return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
	}
	/** Snapshot from a MediaStream via a hidden video element and a canvas. */
	var StreamFrameSource = class {
		constructor(stream, maxWidth, quality) {
			this.stream = stream;
			this.maxWidth = maxWidth;
			this.quality = quality;
			this.video = document.createElement("video");
			this.video.muted = true;
			this.video.playsInline = true;
			this.video.srcObject = stream;
			this.video.play().catch(() => void 0);
		}
		get live() {
			return this.stream.getVideoTracks().some((t) => t.readyState === "live");
		}
		async grab() {
			if (!this.live || this.video.videoWidth === 0) return null;
			const scale = Math.min(1, this.maxWidth / this.video.videoWidth);
			const canvas = document.createElement("canvas");
			canvas.width = Math.round(this.video.videoWidth * scale);
			canvas.height = Math.round(this.video.videoHeight * scale);
			canvas.getContext("2d").drawImage(this.video, 0, 0, canvas.width, canvas.height);
			const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", this.quality));
			return blob ? blob.arrayBuffer() : null;
		}
	};
	/**
	* Sequence numbers come from elapsed seconds since the session epoch, so they stay unique and
	* increasing across a shell reload without any stored counter.
	*/
	function sequenceFor(epochMs, nowMs) {
		return Math.max(0, Math.floor((nowMs - epochMs) / 1e3));
	}
	async function captureOnce(kind, source, queue, epochMs, now = Date.now) {
		const data = await source.grab();
		if (!data) return false;
		const t = now();
		const seq = sequenceFor(epochMs, t);
		await queue.put({
			id: `${kind}-${seq}`,
			kind,
			seq,
			data,
			sha256: await sha256Hex(data),
			capturedAt: new Date(t).toISOString(),
			attempts: 0
		});
		return true;
	}
	// src/events.ts
	var EventCollector = class {
		constructor(api) {
			this.api = api;
			this.buffer = [];
			this.detachers = [];
		}
		record(type, data = {}) {
			this.buffer.push({
				type,
				ts: (/* @__PURE__ */ new Date()).toISOString(),
				data
			});
			if (this.buffer.length > 2e3) this.buffer.splice(0, this.buffer.length - 2e3);
		}
		/** Listen on a window (outer shell or the framed Moodle page). */
		attach(win) {
			const doc = win.document;
			const questionOf = (target) => {
				const q = (target instanceof win.Element ? target : null)?.closest(".que");
				return q?.id ? { question: q.id } : {};
			};
			const on = (target, type, fn) => {
				target.addEventListener(type, fn, true);
				this.detachers.push(() => target.removeEventListener(type, fn, true));
			};
			on(win, "blur", () => this.record("blur"));
			on(win, "focus", () => this.record("focus"));
			on(doc, "visibilitychange", () => this.record(doc.hidden ? "visibility_hidden" : "visibility_visible"));
			on(doc, "fullscreenchange", () => !doc.fullscreenElement && this.record("fullscreen_exit"));
			for (const type of [
				"copy",
				"cut",
				"paste",
				"contextmenu"
			]) on(doc, type, (e) => this.record(type, questionOf(e.target)));
			on(win, "online", () => this.record("online"));
			on(win, "offline", () => this.record("offline"));
			on(win, "resize", () => this.record("resize", {
				w: win.innerWidth,
				h: win.innerHeight
			}));
			doc.querySelectorAll(".que[id]").forEach((q) => this.record("question_shown", { question: q.id }));
		}
		detachAll() {
			this.detachers.splice(0).forEach((d) => d());
		}
		/** Send buffered events. On failure they stay buffered for the next flush. */
		async flush() {
			if (this.buffer.length === 0) return 0;
			const batch = this.buffer.slice(0, 500);
			try {
				await this.api.events(batch);
				this.buffer.splice(0, batch.length);
				return batch.length;
			} catch {
				return 0;
			}
		}
		get pending() {
			return this.buffer.length;
		}
	};
	// src/queue.ts
	var MemoryQueue = class {
		constructor() {
			this.items = /* @__PURE__ */ new Map();
		}
		async put(item) {
			this.items.set(item.id, item);
		}
		async oldest(limit) {
			return [...this.items.values()].sort((a, b) => a.capturedAt.localeCompare(b.capturedAt)).slice(0, limit);
		}
		async remove(id) {
			this.items.delete(id);
		}
		async size() {
			return this.items.size;
		}
	};
	var STORE = "uploads";
	function request(req) {
		return new Promise((resolve, reject) => {
			req.onsuccess = () => resolve(req.result);
			req.onerror = () => reject(req.error);
		});
	}
	var IndexedDbQueue = class IndexedDbQueue {
		constructor(db) {
			this.db = db;
		}
		static async open(name) {
			const req = indexedDB.open(name, 1);
			req.onupgradeneeded = () => {
				req.result.createObjectStore(STORE, { keyPath: "id" }).createIndex("capturedAt", "capturedAt");
			};
			return new IndexedDbQueue(await request(req));
		}
		store(mode) {
			return this.db.transaction(STORE, mode).objectStore(STORE);
		}
		async put(item) {
			await request(this.store("readwrite").put(item));
		}
		async oldest(limit) {
			return request(this.store("readonly").index("capturedAt").getAll(null, limit));
		}
		async remove(id) {
			await request(this.store("readwrite").delete(id));
		}
		async size() {
			return request(this.store("readonly").count());
		}
	};
	/** IndexedDB queue per session, falling back to memory (private windows, old browsers). */
	async function openQueue(sessionId) {
		try {
			if (typeof indexedDB !== "undefined") return await IndexedDbQueue.open(`examproctor-${sessionId}`);
		} catch {}
		return new MemoryQueue();
	}
	// src/uploader.ts
	/** Drains the upload queue: presign -> PUT -> complete, with backoff while offline. */
	/** Errors that will never succeed on retry: drop the item and report it. */
	var PERMANENT = /* @__PURE__ */ new Set([
		"too_large",
		"kind_not_in_policy",
		"session_purged",
		"seq_conflict",
		"bad_sha256"
	]);
	var Uploader = class {
		constructor(deps) {
			this.deps = deps;
			this.failures = 0;
		}
		/** Delay before the next drain, in ms: 1 s when healthy, doubling to 60 s while failing. */
		get nextDelayMs() {
			return this.failures === 0 ? 1e3 : Math.min(1e3 * 2 ** this.failures, 6e4);
		}
		/** Upload what is queued. Stops at the first network failure (keeps order, avoids hammering). */
		async drain(batch = 5) {
			let done = 0;
			for (const item of await this.deps.queue.oldest(batch)) try {
				const presigned = await this.deps.api.presign({
					kind: item.kind,
					bytes: item.data.byteLength,
					sha256: item.sha256,
					seq: item.seq,
					captured_at: item.capturedAt
				});
				if (!presigned.already_uploaded) {
					await this.deps.api.put(presigned.url, item.data, presigned.headers);
					await this.deps.api.complete(presigned.key);
				}
				await this.deps.queue.remove(item.id);
				done += 1;
				this.failures = 0;
			} catch (error) {
				if (error instanceof ApiError && PERMANENT.has(error.code)) {
					await this.deps.queue.remove(item.id);
					this.deps.onDropped?.(item.id, error.code);
					continue;
				}
				this.failures += 1;
				await this.deps.queue.put({
					...item,
					attempts: item.attempts + 1
				});
				break;
			}
			return done;
		}
	};
	// src/shell.ts
	var ATTEMPT_PAGES = /\/mod\/quiz\/(attempt|summary|startattempt|processattempt)\.php$/;
	var ExamShell = class {
		constructor(deps) {
			this.deps = deps;
			this.timers = [];
			this.epoch = Date.now();
			this.stopped = false;
			this.frameBroken = false;
			this.events = new EventCollector(deps.api);
			this.uploader = new Uploader({
				api: deps.api,
				queue: deps.queue,
				onDropped: (id, code) => this.events.record("capture_error", {
					id,
					code
				})
			});
		}
		/** Submit the (already validated) preflight form into the shell frame and start capture. */
		start(form) {
			const name = "examproctor-shell-frame";
			const overlay = document.createElement("div");
			overlay.id = "examproctor-shell";
			overlay.setAttribute("style", "position:fixed;inset:0;z-index:100000;background:#fff;display:flex;flex-direction:column");
			this.status = document.createElement("div");
			this.status.setAttribute("role", "status");
			this.status.setAttribute("style", `padding:4px 12px;font:14px sans-serif;background:${this.deps.staging ? "#ff7f50" : "#037b90"};color:#fff`);
			this.status.textContent = this.deps.text.capturing;
			this.iframe = document.createElement("iframe");
			this.iframe.name = name;
			this.iframe.title = "Quiz";
			this.iframe.setAttribute("style", "flex:1;border:0;width:100%");
			overlay.append(this.status, this.iframe);
			document.body.append(overlay);
			this.iframe.addEventListener("load", () => this.onFrameLoad());
			form.target = name;
			HTMLFormElement.prototype.submit.call(form);
			this.events.attach(window);
			this.events.record("shell_loaded");
			this.watchStream(this.deps.screen, "screen");
			this.watchStream(this.deps.camera, "camera");
			this.startLoops();
		}
		watchStream(stream, kind) {
			stream?.getVideoTracks().forEach((track) => track.addEventListener("ended", () => {
				this.events.record("stream_ended", { kind });
				if (kind === "screen" && this.status) this.status.textContent = this.deps.text.screenStopped;
			}));
		}
		onFrameLoad() {
			const win = this.iframe?.contentWindow;
			if (!win) return;
			let href;
			try {
				href = win.location.href;
			} catch {
				this.frameBroken = true;
				this.events.record("connectivity_gap", { frame: "unreadable" });
				if (this.status) this.status.textContent = this.deps.text.reconnecting;
				return;
			}
			if (ATTEMPT_PAGES.test(new URL(href).pathname)) {
				this.frameBroken = false;
				this.lastGoodUrl = href;
				if (this.status) this.status.textContent = this.deps.text.capturing;
				this.events.attach(win);
				return;
			}
			this.events.record("attempt_left", { path: new URL(href).pathname });
			if (this.status) this.status.textContent = this.deps.text.leaving;
			this.stop().finally(() => window.location.assign(href));
		}
		every(ms, fn) {
			this.timers.push(window.setInterval(() => void fn(), ms));
		}
		startLoops() {
			const sources = [];
			if (this.deps.camera) sources.push([
				"camera",
				new StreamFrameSource(this.deps.camera, 640, .6),
				this.deps.policy.camera_interval_s ?? 30
			]);
			if (this.deps.screen) sources.push([
				"screen",
				new StreamFrameSource(this.deps.screen, 1280, .5),
				this.deps.policy.screen_interval_s ?? 60
			]);
			for (const [kind, source, seconds] of sources) this.every(seconds * 1e3, () => captureOnce(kind, source, this.deps.queue, this.epoch));
			const drain = async () => {
				if (this.stopped) return;
				await this.uploader.drain();
				this.timers.push(window.setTimeout(drain, this.uploader.nextDelayMs));
			};
			drain();
			this.every(5e3, () => this.events.flush());
			const recover = () => {
				if (this.frameBroken && navigator.onLine && this.iframe && this.lastGoodUrl) {
					this.frameBroken = false;
					this.iframe.src = this.lastGoodUrl;
				}
			};
			window.addEventListener("online", recover);
			this.every(5e3, recover);
			this.every(1e4, async () => this.deps.api.heartbeat({
				queued_uploads: await this.deps.queue.size(),
				camera_live: this.deps.camera?.getVideoTracks().some((t) => t.readyState === "live") ?? null,
				screen_live: this.deps.screen?.getVideoTracks().some((t) => t.readyState === "live") ?? null
			}).catch(() => this.events.record("connectivity_gap")));
		}
		/** Stop capture, try to send what is queued (up to 10 s), close the session, release devices. */
		async stop() {
			if (this.stopped) return;
			this.stopped = true;
			this.timers.splice(0).forEach((t) => {
				clearInterval(t);
				clearTimeout(t);
			});
			const deadline = Date.now() + 1e4;
			while (Date.now() < deadline && await this.deps.queue.size() > 0) if (await this.uploader.drain(10) === 0) break;
			await this.events.flush();
			await this.deps.api.finish().catch(() => void 0);
			this.events.detachAll();
			[this.deps.camera, this.deps.screen].forEach((s) => s?.getTracks().forEach((t) => t.stop()));
		}
	};
	// src/i18n.ts
	/** Candidate-facing text in English and Swahili. Keys are stable; text may change with the consent version. */
	var en = {
		title: "Before you start",
		consent: "This quiz is proctored. With your agreement, ExamProctor takes photos from your camera and, on a computer, snapshots of your whole screen during the attempt. It also records when you leave the quiz page. It never records what you type. Your teacher and exam officers review the results. AI only raises flags for a person to check; it never fails you by itself. Data is kept in Kenya for 90 days after results are final.",
		agree: "I agree",
		camera: "Allow camera",
		screen: "Share your whole screen",
		check: "Run the checks",
		ok: "Done",
		denied: "Permission refused. Allow it in your browser settings and try again.",
		missing: "No device found.",
		unsupported: "Not available on this device.",
		waiting: "Checks passed. Unlocking your quiz…",
		ready: "All checks passed. You can start the attempt.",
		blocked: "You cannot start yet:",
		retry: "Try again",
		error: "Something went wrong. Reload the page and try again.",
		staging: "Staging: synthetic data only",
		reason_camera_denied: "Camera permission was refused.",
		reason_camera_missing: "No camera was found.",
		reason_camera_unsupported: "This device cannot use a camera here.",
		reason_screen_denied: "Screen sharing was refused.",
		reason_screen_missing: "Screen sharing failed.",
		reason_screen_unsupported: "This device cannot share its screen. Use a computer.",
		reason_screen_not_whole_display: "Share your entire screen, not a window or a tab.",
		reason_network_unavailable: "The connection to the proctoring service failed.",
		capturing: "ExamProctor is on: camera and screen snapshots are being taken.",
		screen_stopped: "Screen sharing has stopped. Reload the quiz page to share your screen again.",
		leaving: "Saving proctoring data…",
		reconnecting: "Connection lost. Your answers are safe in Moodle; the quiz page will reload when you are back online."
	};
	var sw = {
		title: "Kabla ya kuanza",
		consent: "Jaribio hili linasimamiwa. Kwa idhini yako, ExamProctor itapiga picha kupitia kamera yako na, kwenye kompyuta, picha za skrini yako yote wakati wa jaribio. Pia hurekodi unapotoka kwenye ukurasa wa jaribio. Haiandiki chochote unachokichapa. Mwalimu wako na maafisa wa mitihani hukagua matokeo. AI huibua tu alama za kukaguliwa na mtu; haikufelishi yenyewe. Data huhifadhiwa nchini Kenya kwa siku 90 baada ya matokeo kuthibitishwa.",
		agree: "Ninakubali",
		camera: "Ruhusu kamera",
		screen: "Shiriki skrini yako yote",
		check: "Fanya ukaguzi",
		ok: "Imekamilika",
		denied: "Ruhusa imekataliwa. Iruhusu kwenye mipangilio ya kivinjari kisha ujaribu tena.",
		missing: "Kifaa hakijapatikana.",
		unsupported: "Haipatikani kwenye kifaa hiki.",
		waiting: "Ukaguzi umefaulu. Tunafungua jaribio lako…",
		ready: "Ukaguzi wote umefaulu. Unaweza kuanza jaribio.",
		blocked: "Huwezi kuanza bado:",
		retry: "Jaribu tena",
		error: "Hitilafu imetokea. Pakia ukurasa upya kisha ujaribu tena.",
		staging: "Majaribio: data bandia pekee",
		reason_camera_denied: "Ruhusa ya kamera imekataliwa.",
		reason_camera_missing: "Kamera haijapatikana.",
		reason_camera_unsupported: "Kifaa hiki hakiwezi kutumia kamera hapa.",
		reason_screen_denied: "Kushiriki skrini kumekataliwa.",
		reason_screen_missing: "Kushiriki skrini kumeshindwa.",
		reason_screen_unsupported: "Kifaa hiki hakiwezi kushiriki skrini. Tumia kompyuta.",
		reason_screen_not_whole_display: "Shiriki skrini nzima, si dirisha au kichupo.",
		reason_network_unavailable: "Muunganisho na huduma ya usimamizi umeshindwa.",
		capturing: "ExamProctor imewashwa: picha za kamera na skrini zinachukuliwa.",
		screen_stopped: "Kushiriki skrini kumesimama. Pakia upya ukurasa wa jaribio ili kushiriki skrini tena.",
		leaving: "Tunahifadhi data ya usimamizi…",
		reconnecting: "Muunganisho umepotea. Majibu yako yako salama kwenye Moodle; ukurasa wa jaribio utapakia upya mtandao ukirudi."
	};
	function strings(lang) {
		return lang.toLowerCase().startsWith("sw") ? sw : en;
	}
	// src/ui.ts
	/** Mounts the pre-check panel inside the Moodle preflight form. Plain DOM, no framework. */
	function el(tag, text, attrs = {}) {
		const node = document.createElement(tag);
		if (text) node.textContent = text;
		Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
		return node;
	}
	async function mountPrecheck(options) {
		const root = document.querySelector(options.container);
		if (!root) return;
		const t = strings(options.lang);
		const form = root.closest("form");
		const submit = form?.querySelector("[type=submit][name=submitbutton]");
		if (submit) submit.disabled = true;
		const api = new SessionApi(options.serviceUrl);
		const controller = new PrecheckController({
			api,
			media: navigator.mediaDevices,
			caps: detectCapabilities()
		});
		root.replaceChildren();
		if (options.staging) root.append(el("div", t.staging, { class: "alert alert-warning" }));
		const message = el("div", "", {
			role: "status",
			"aria-live": "polite",
			class: "mt-2"
		});
		try {
			await controller.start(options.launchToken);
		} catch {
			root.append(el("div", t.error, { class: "alert alert-danger" }));
			return;
		}
		const consentBox = el("div", "", { class: "mb-3" });
		consentBox.append(el("h4", t.title), el("p", t.consent));
		const agree = el("button", t.agree, {
			type: "button",
			class: "btn btn-primary"
		});
		consentBox.append(agree);
		root.append(consentBox);
		const devices = el("div", "", {
			class: "mb-3",
			hidden: ""
		});
		const checkButton = el("button", t.check, {
			type: "button",
			class: "btn btn-primary mt-2",
			hidden: ""
		});
		root.append(devices, checkButton, message);
		const deviceRow = (label, run) => {
			const row = el("div", "", { class: "d-flex align-items-center gap-2 mb-2" });
			const button = el("button", t[label], {
				type: "button",
				class: "btn btn-secondary"
			});
			const state = el("span");
			button.addEventListener("click", async () => {
				button.disabled = true;
				const result = await run();
				state.textContent = result.status === "ok" ? t.ok : t[result.status] ?? result.status;
				button.disabled = result.status === "ok";
				checkButton.hidden = controller.pendingDevices().length > 0;
			});
			row.append(button, state);
			devices.append(row);
		};
		agree.addEventListener("click", async () => {
			agree.disabled = true;
			try {
				await controller.consent();
			} catch {
				message.textContent = t.error;
				return;
			}
			if (controller.policy.camera) deviceRow("camera", () => controller.requestCamera());
			if (controller.policy.screen && !detectCapabilities().isMobile) deviceRow("screen", () => controller.requestScreen());
			devices.hidden = false;
			checkButton.hidden = controller.pendingDevices().length > 0;
		});
		checkButton.addEventListener("click", async () => {
			checkButton.disabled = true;
			message.textContent = t.waiting;
			try {
				const outcome = await controller.submit();
				if (outcome.kind === "ready") {
					message.textContent = t.ready;
					if (submit) submit.disabled = false;
					const queue = await openQueue(controller.session.session_id);
					form?.addEventListener("submit", (event) => {
						event.preventDefault();
						new ExamShell({
							api,
							policy: controller.policy,
							queue,
							camera: controller.camera.stream,
							screen: controller.screen.stream,
							staging: options.staging,
							text: {
								capturing: t.capturing,
								screenStopped: t.screen_stopped,
								leaving: t.leaving,
								reconnecting: t.reconnecting
							}
						}).start(form);
					}, { once: true });
					return;
				}
				if (outcome.kind === "blocked") {
					message.replaceChildren(el("p", t.blocked));
					const list = el("ul");
					outcome.reasons.forEach((r) => list.append(el("li", t[`reason_${r}`] ?? r)));
					message.append(list);
				} else message.textContent = t.error;
			} catch (error) {
				message.textContent = error instanceof ApiError ? `${t.error} (${error.code})` : t.error;
			}
			checkButton.disabled = false;
			checkButton.textContent = t.retry;
		});
	}
	// src/index.ts
	var SDK_VERSION = "0.3.0";
	exports.ApiError = ApiError;
	exports.EventCollector = EventCollector;
	exports.ExamShell = ExamShell;
	exports.MemoryQueue = MemoryQueue;
	exports.PrecheckController = PrecheckController;
	exports.SDK_VERSION = SDK_VERSION;
	exports.SessionApi = SessionApi;
	exports.Uploader = Uploader;
	exports.captureOnce = captureOnce;
	exports.detectCapabilities = detectCapabilities;
	exports.mountPrecheck = mountPrecheck;
	exports.openQueue = openQueue;
	exports.sequenceFor = sequenceFor;
	exports.sha256Hex = sha256Hex;
});
