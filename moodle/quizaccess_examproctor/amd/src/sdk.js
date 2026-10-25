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
		/** Ask the service to decide, then wait until it has told Moodle. Streams are released. */
		async submit() {
			let status = await this.deps.api.precheck(this.results());
			stopStream(this.camera.stream);
			stopStream(this.screen.stream);
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
		reason_network_unavailable: "The connection to the proctoring service failed."
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
		reason_network_unavailable: "Muunganisho na huduma ya usimamizi umeshindwa."
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
		const submit = root.closest("form")?.querySelector("[type=submit][name=submitbutton]");
		if (submit) submit.disabled = true;
		const controller = new PrecheckController({
			api: new SessionApi(options.serviceUrl),
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
	var SDK_VERSION = "0.2.0";
	exports.ApiError = ApiError;
	exports.PrecheckController = PrecheckController;
	exports.SDK_VERSION = SDK_VERSION;
	exports.SessionApi = SessionApi;
	exports.detectCapabilities = detectCapabilities;
	exports.mountPrecheck = mountPrecheck;
});
