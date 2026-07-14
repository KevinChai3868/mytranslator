async function checkHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();
        console.log("API health:", data);
    } catch (error) {
        console.error("API health check failed:", error);
    }
}

class Recognizer {
    constructor({ getLanguage, onInterim, onDone, onError }) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        this.supported = Boolean(SpeechRecognition);
        this.recognition = this.supported ? new SpeechRecognition() : null;
        this.getLanguage = getLanguage;
        this.onInterim = onInterim;
        this.onDone = onDone;
        this.onError = onError;
        this.isListening = false;
        this.shouldRestart = false;
        this.isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
        this.finalText = "";
        this.currentText = "";

        if (!this.supported) {
            return;
        }

        this.recognition.continuous = !this.isMobile;
        this.recognition.interimResults = true;
        this.recognition.maxAlternatives = 1;

        this.recognition.onresult = (event) => {
            let interimText = "";

            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const transcript = event.results[i][0].transcript;

                if (event.results[i].isFinal) {
                    this.finalText = `${this.finalText} ${transcript}`.trim();
                } else {
                    interimText += transcript;
                }
            }

            const wholeText = `${this.finalText} ${interimText}`.trim();
            this.currentText = wholeText;
            this.onInterim(wholeText);
        };

        this.recognition.onerror = (event) => {
            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                this.shouldRestart = false;
                this.isListening = false;
                this.onError("麥克風權限被拒絕，請允許瀏覽器使用麥克風後再試一次。");
                return;
            }

            if (event.error === "no-speech") {
                return;
            }

            if (event.error === "audio-capture") {
                this.shouldRestart = false;
                this.isListening = false;
                this.onError("手機沒有取得麥克風音訊，請確認瀏覽器麥克風權限已允許。");
                return;
            }

            this.onError(`語音辨識發生問題：${event.error}`);
        };

        this.recognition.onend = () => {
            this.isListening = false;

            if (this.isMobile) {
                const doneText = (this.currentText || this.finalText).trim();
                this.shouldRestart = false;

                if (doneText) {
                    this.onDone(doneText);
                }

                this.finalText = "";
                this.currentText = "";
                return;
            }

            if (!this.shouldRestart) {
                return;
            }

            window.setTimeout(() => {
                if (this.shouldRestart) {
                    this.start();
                }
            }, 250);
        };
    }

    start() {
        if (!this.supported) {
            this.onError("這個瀏覽器不支援 Web Speech API，請改用 Chrome 或 Edge。");
            return false;
        }

        if (this.isListening) {
            return true;
        }

        try {
            this.recognition.lang = this.getLanguage();
            this.shouldRestart = true;
            this.isListening = true;
            this.recognition.start();
            return true;
        } catch (error) {
            this.isListening = false;
            this.shouldRestart = false;
            this.onError("語音辨識無法啟動。請用 Chrome 或 Edge 開啟 HTTPS 網址，並允許麥克風權限；不要用 LINE 或 Facebook 內建瀏覽器。");
            console.error("Speech recognition start failed:", error);
            return false;
        }
    }

    stop() {
        if (!this.supported || !this.isListening) {
            return;
        }

        this.shouldRestart = false;
        this.isListening = false;
        this.recognition.stop();

        const doneText = (this.currentText || this.finalText).trim();
        if (doneText) {
            this.onDone(doneText);
        }

        this.finalText = "";
        this.currentText = "";
    }

    toggle() {
        if (this.isListening) {
            this.stop();
            return false;
        }

        return this.start();
    }
}

function setupLanguageSwap() {
    const languageA = document.querySelector("#language-a");
    const languageB = document.querySelector("#language-b");
    const swapButton = document.querySelector("#swap-languages");

    if (!languageA || !languageB || !swapButton) {
        return;
    }

    swapButton.addEventListener("click", () => {
        const oldLanguageA = languageA.value;
        languageA.value = languageB.value;
        languageB.value = oldLanguageA;

        swapButton.classList.add("is-swapping");
        window.setTimeout(() => {
            swapButton.classList.remove("is-swapping");
        }, 180);
    });
}

function setupToolTabs() {
    const tabs = Array.from(document.querySelectorAll("[data-tool-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-tool-panel]"));

    if (!tabs.length || !panels.length) {
        return;
    }

    const activate = (toolName) => {
        tabs.forEach((tab) => {
            const isActive = tab.dataset.toolTab === toolName;
            tab.classList.toggle("is-active", isActive);
            tab.setAttribute("aria-selected", String(isActive));
        });

        panels.forEach((panel) => {
            panel.classList.toggle("is-active", panel.dataset.toolPanel === toolName);
        });
    };

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => activate(tab.dataset.toolTab));
    });

    activate("text");
}

async function translateText({ text, source, target, resultText, translateButton }) {
    const speakButton = document.querySelector("#speak-result");

    if (!text) {
        resultText.textContent = "請先輸入想翻譯的文字。";
        if (speakButton) {
            speakButton.disabled = true;
        }
        return;
    }

    resultText.textContent = "翻譯中...";
    if (speakButton) {
        speakButton.disabled = true;
    }
    if (translateButton) {
        translateButton.disabled = true;
        translateButton.textContent = "翻譯中";
    }

    try {
        const response = await fetch("/api/translate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                text,
                source,
                target,
            }),
        });

        const data = await response.json();
        if (data.ok) {
            resultText.textContent = data.translation;
            if (speakButton) {
                speakButton.disabled = !data.translation;
            }
        } else {
            resultText.textContent = data.error || "翻譯失敗，請稍後再試。";
            if (speakButton) {
                speakButton.disabled = true;
            }
        }
    } catch (error) {
        console.error("Translate failed:", error);
        resultText.textContent = "無法連線到翻譯 API，請確認 Flask 是否正在執行。";
        if (speakButton) {
            speakButton.disabled = true;
        }
    } finally {
        if (translateButton) {
            translateButton.disabled = false;
            translateButton.textContent = "翻譯";
        }
    }
}

function setupTranslateForm() {
    const form = document.querySelector("#translate-form");
    const sourceText = document.querySelector("#source-text");
    const languageA = document.querySelector("#language-a");
    const languageB = document.querySelector("#language-b");
    const resultText = document.querySelector("#translation-result");
    const translateButton = document.querySelector("#translate-button");

    if (!form || !sourceText || !languageA || !languageB || !resultText || !translateButton) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await translateText({
            text: sourceText.value.trim(),
            source: languageA.value,
            target: languageB.value,
            resultText,
            translateButton,
        });
    });
}

function setupTextToSpeech() {
    const speakButton = document.querySelector("#speak-result");
    const resultText = document.querySelector("#translation-result");
    let currentAudioUrl = "";

    if (!speakButton || !resultText) {
        return;
    }

    speakButton.addEventListener("click", async () => {
        const text = resultText.textContent.trim();
        if (!text || speakButton.disabled) {
            return;
        }

        speakButton.disabled = true;
        speakButton.textContent = "產生中";

        try {
            const response = await fetch("/api/tts", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ text }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || "朗讀失敗，請稍後再試。");
            }

            const audioBlob = await response.blob();
            if (currentAudioUrl) {
                URL.revokeObjectURL(currentAudioUrl);
            }

            currentAudioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(currentAudioUrl);
            speakButton.textContent = "播放中";

            audio.addEventListener("ended", () => {
                speakButton.disabled = false;
                speakButton.textContent = "朗讀";
            });

            audio.addEventListener("error", () => {
                speakButton.disabled = false;
                speakButton.textContent = "朗讀";
                resultText.textContent = "音訊播放失敗，請再試一次。";
            });

            await audio.play();
        } catch (error) {
            console.error("TTS failed:", error);
            resultText.textContent = error.message || "朗讀失敗，請稍後再試。";
            speakButton.disabled = false;
            speakButton.textContent = "朗讀";
        }
    });
}

function readImageAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const image = new Image();
        const reader = new FileReader();

        reader.onload = () => {
            image.onload = () => {
                const maxSize = 1400;
                const scale = Math.min(1, maxSize / Math.max(image.width, image.height));
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(image.width * scale));
                canvas.height = Math.max(1, Math.round(image.height * scale));

                const context = canvas.getContext("2d");
                context.drawImage(image, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL("image/jpeg", 0.86));
            };

            image.onerror = () => reject(new Error("圖片讀取失敗，請換一張照片再試。"));
            image.src = reader.result;
        };

        reader.onerror = () => reject(new Error("圖片讀取失敗，請換一張照片再試。"));
        reader.readAsDataURL(file);
    });
}

function setupPhotoTranslation() {
    const cameraInput = document.querySelector("#camera-input");
    const uploadInput = document.querySelector("#upload-input");
    const photoPreview = document.querySelector("#photo-preview");
    const photoButton = document.querySelector("#translate-photo-button");
    const languageB = document.querySelector("#language-b");
    const resultText = document.querySelector("#translation-result");
    const speakButton = document.querySelector("#speak-result");
    let currentImageDataUrl = "";

    if (!cameraInput || !uploadInput || !photoPreview || !photoButton || !languageB || !resultText) {
        return;
    }

    const handlePhotoSelected = async (input) => {
        const file = input.files && input.files[0];
        currentImageDataUrl = "";
        photoButton.disabled = true;

        if (!file) {
            photoPreview.hidden = true;
            return;
        }

        if (!file.type.startsWith("image/")) {
            resultText.textContent = "請選擇圖片檔。";
            photoPreview.hidden = true;
            return;
        }

        resultText.textContent = "正在讀取照片...";
        if (speakButton) {
            speakButton.disabled = true;
        }

        try {
            currentImageDataUrl = await readImageAsDataUrl(file);
            photoPreview.src = currentImageDataUrl;
            photoPreview.hidden = false;
            photoButton.disabled = false;
            resultText.textContent = "照片已載入，可以按「翻譯照片」。";
        } catch (error) {
            console.error("Image read failed:", error);
            resultText.textContent = error.message || "圖片讀取失敗，請換一張照片再試。";
            photoPreview.hidden = true;
        }
    };

    cameraInput.addEventListener("change", () => handlePhotoSelected(cameraInput));
    uploadInput.addEventListener("change", () => handlePhotoSelected(uploadInput));

    photoButton.addEventListener("click", async () => {
        if (!currentImageDataUrl) {
            resultText.textContent = "請先拍照或選擇圖片。";
            return;
        }

        photoButton.disabled = true;
        photoButton.textContent = "辨識中";
        resultText.textContent = "正在辨識並翻譯照片文字...";
        if (speakButton) {
            speakButton.disabled = true;
        }

        try {
            const response = await fetch("/api/translate-image", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    image: currentImageDataUrl,
                    target: languageB.value,
                }),
            });

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || "照片翻譯失敗，請稍後再試。");
            }

            const summary = data.summary ? `摘要：\n${data.summary}` : "";
            const translation = data.translation ? `翻譯：\n${data.translation}` : "";
            resultText.textContent = [summary, translation].filter(Boolean).join("\n\n");
            if (speakButton) {
                speakButton.disabled = !data.translation;
            }
        } catch (error) {
            console.error("Photo translation failed:", error);
            resultText.textContent = error.message || "照片翻譯失敗，請稍後再試。";
        } finally {
            photoButton.disabled = false;
            photoButton.textContent = "翻譯照片";
        }
    });
}

function setupTravelAssistant() {
    const questionInput = document.querySelector("#assistant-question");
    const askButton = document.querySelector("#assistant-button");
    const assistantResult = document.querySelector("#assistant-result");
    const mainResult = document.querySelector("#translation-result");
    const speakButton = document.querySelector("#speak-result");

    if (!questionInput || !askButton || !assistantResult || !mainResult) {
        return;
    }

    const ask = async () => {
        const question = questionInput.value.trim();
        if (!question) {
            assistantResult.textContent = "請先輸入旅遊問題。";
            return;
        }

        askButton.disabled = true;
        askButton.textContent = "思考中";
        assistantResult.textContent = "正在整理旅行建議...";
        mainResult.textContent = "旅遊助手思考中...";
        if (speakButton) {
            speakButton.disabled = true;
        }

        try {
            const response = await fetch("/api/ask", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ question }),
            });

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || "旅遊助手暫時無法回答，請稍後再試。");
            }

            const sourceLines = (data.sources || [])
                .slice(0, 3)
                .map((source, index) => `${index + 1}. ${source.title || source.url}\n${source.url}`)
                .join("\n");
            const sourceText = sourceLines ? `\n\n來源：\n${sourceLines}` : "";
            const searchText = data.searched ? "已參考即時搜尋。\n\n" : "";
            const answerText = `${searchText}${data.answer}${sourceText}`;

            assistantResult.textContent = answerText;
            mainResult.textContent = data.answer;
            if (speakButton) {
                speakButton.disabled = !data.answer;
            }
        } catch (error) {
            console.error("Travel assistant failed:", error);
            assistantResult.textContent = error.message || "旅遊助手暫時無法回答，請稍後再試。";
            mainResult.textContent = assistantResult.textContent;
            if (speakButton) {
                speakButton.disabled = true;
            }
        } finally {
            askButton.disabled = false;
            askButton.textContent = "問助手";
        }
    };

    askButton.addEventListener("click", ask);
    questionInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            ask();
        }
    });
}

function formatCurrencyValue(value, currency) {
    const numericValue = Number(value);
    const maximumFractionDigits = currency === "JPY" ? 0 : 2;

    return new Intl.NumberFormat("zh-TW", {
        style: "currency",
        currency,
        maximumFractionDigits,
    }).format(numericValue);
}

function setupCurrencyConverter() {
    const amountInput = document.querySelector("#currency-amount");
    const sourceSelect = document.querySelector("#currency-source");
    const targetSelect = document.querySelector("#currency-target");
    const convertButton = document.querySelector("#currency-button");
    const swapButton = document.querySelector("#swap-currency");
    const resultText = document.querySelector("#currency-result");

    if (!amountInput || !sourceSelect || !targetSelect || !convertButton || !swapButton || !resultText) {
        return;
    }

    const convert = async () => {
        const amount = amountInput.value.trim();
        if (!amount) {
            resultText.textContent = "請先輸入要換算的金額。";
            return;
        }

        convertButton.disabled = true;
        convertButton.textContent = "換算中";
        resultText.textContent = "正在取得最新匯率...";

        try {
            const response = await fetch("/api/currency", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    amount,
                    source: sourceSelect.value,
                    target: targetSelect.value,
                }),
            });

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || "匯率換算失敗，請稍後再試。");
            }

            const fromText = formatCurrencyValue(data.amount, data.source);
            const toText = formatCurrencyValue(data.converted, data.target);
            const rateText = Number(data.rate).toLocaleString("zh-TW", {
                maximumFractionDigits: 6,
            });
            resultText.textContent = `${fromText} ≈ ${toText}，1 ${data.source} = ${rateText} ${data.target}`;
        } catch (error) {
            console.error("Currency conversion failed:", error);
            resultText.textContent = error.message || "匯率換算失敗，請稍後再試。";
        } finally {
            convertButton.disabled = false;
            convertButton.textContent = "換算";
        }
    };

    convertButton.addEventListener("click", convert);
    amountInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            convert();
        }
    });

    swapButton.addEventListener("click", () => {
        const oldSource = sourceSelect.value;
        sourceSelect.value = targetSelect.value;
        targetSelect.value = oldSource;
        convert();
    });
}

function setupWeatherLookup() {
    const locationInput = document.querySelector("#weather-location");
    const weatherButton = document.querySelector("#weather-button");
    const resultBox = document.querySelector("#weather-result");

    if (!locationInput || !weatherButton || !resultBox) {
        return;
    }

    const lookup = async () => {
        const location = locationInput.value.trim();
        if (!location) {
            resultBox.textContent = "請先輸入城市名稱，例如：那霸、東京。";
            return;
        }

        weatherButton.disabled = true;
        weatherButton.textContent = "查詢中";
        resultBox.textContent = "正在向 Open-Meteo 查詢天氣...";

        try {
            const response = await fetch("/api/weather", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ location }),
            });

            const data = await response.json();
            if (!data.ok) {
                throw new Error(data.error || "天氣查詢失敗，請稍後再試。");
            }

            const place = [data.location, data.admin1, data.country]
                .filter(Boolean)
                .join("，");
            resultBox.innerHTML = `
                <div class="weather-place">${place}</div>
                <div class="weather-main">${Math.round(data.temperature)}°C · ${data.weather}</div>
                <div class="weather-details">
                    <span>體感 ${Math.round(data.apparent_temperature)}°C</span>
                    <span>濕度 ${data.humidity}%</span>
                    <span>降雨 ${data.rain_probability}%</span>
                </div>
                <div class="weather-advice">${data.advice}</div>
            `;
        } catch (error) {
            console.error("Weather lookup failed:", error);
            resultBox.textContent = error.message || "天氣查詢失敗，請稍後再試。";
        } finally {
            weatherButton.disabled = false;
            weatherButton.textContent = "查詢天氣";
        }
    };

    weatherButton.addEventListener("click", lookup);
    locationInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            lookup();
        }
    });
}

function setupSpeechRecognizer() {
    const micButton = document.querySelector(".mic-button");
    const sourceText = document.querySelector("#source-text");
    const languageA = document.querySelector("#language-a");
    const languageB = document.querySelector("#language-b");
    const resultText = document.querySelector("#translation-result");
    const translateButton = document.querySelector("#translate-button");

    if (!micButton || !sourceText || !languageA || !languageB || !resultText) {
        return;
    }

    const recognizer = new Recognizer({
        getLanguage: () => languageA.value,
        onInterim: (text) => {
            sourceText.value = text;
        },
        onDone: async (text) => {
            sourceText.value = text;
            await translateText({
                text,
                source: languageA.value,
                target: languageB.value,
                resultText,
                translateButton,
            });
        },
        onError: (message) => {
            resultText.textContent = message;
            window.alert(message);
            micButton.classList.remove("is-listening");
            micButton.setAttribute("aria-label", "開始語音輸入");
        },
    });

    micButton.addEventListener("click", () => {
        const isListening = recognizer.toggle();
        micButton.classList.toggle("is-listening", isListening);
        micButton.setAttribute("aria-label", isListening ? "停止語音輸入" : "開始語音輸入");

        if (isListening) {
            sourceText.value = "";
            resultText.textContent = "正在聽你說話...";
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    setupToolTabs();
    setupLanguageSwap();
    setupTranslateForm();
    setupTextToSpeech();
    setupPhotoTranslation();
    setupTravelAssistant();
    setupCurrencyConverter();
    setupWeatherLookup();
    setupSpeechRecognizer();
});

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch((error) => {
            console.warn("Service worker registration failed:", error);
        });
    });
}
