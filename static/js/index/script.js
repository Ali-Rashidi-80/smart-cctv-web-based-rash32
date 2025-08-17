class SmartCameraSystem {
    constructor() {
        this.websocket = null;
        this.isStreaming = false;
        this.deviceMode = 'desktop';
        this.currentPage = 0;
        this.currentVideoPage = 0;
        this.isLoading = false;
        this.retryCount = 0;
        this.maxRetries = 5;
        this.retryDelay = 2000;
        this.language = localStorage.getItem('language') || 'fa';
        this.systemStatus = {
            websocket: 'disconnected',
            server: 'offline',
            camera: 'offline',
            pico: 'offline'
        };
        this.resolution = { desktop: { width: 1072, height: 603 }, mobile: { width: 536, height: 301 } };
        this.connectionErrorShown = false;
        this.activeErrorNotification = null;
        this.translations = window.translations || {};
        
        // Enhanced memory management
        this.objectUrls = new Set();
        this.cleanupCallbacks = [];
        this.videoElements = new WeakMap();
        this.modalState = {
            isOpen: false,
            currentVideo: null,
            currentImage: null
        };
        
        // Video management
        this.videoCache = new Map();
        this.activeVideos = new Set();
        this.videoEventListeners = new Map();
        this.videoObservers = new Map();
        this.deletingVideos = new Set(); // Track videos being deleted to prevent duplicates
        this.deletingPhotos = new Set(); // Track photos being deleted to prevent duplicates
        
        // System state management
        this.isSystemBusy = false; // Prevent multiple operations
        this.deletionQueue = []; // Queue for large video deletions
        this.isDeletingVideo = false; // Prevent modal reopening during deletion
        this.deletedVideos = new Set(); // Track successfully deleted videos
        this.reconnectTimer = null;
        this.isConnected = false;
        this.connectionCooldown = 5000; // 5 second cooldown between connection attempts
        this.lastConnectionAttempt = 0;
    }

    // Main entry: load settings from server/localStorage and apply to UI before anything else
    async init() {
        try {
            // Clear deleted videos set on fresh page load
            this.deletedVideos.clear();
            console.log('🧹 Cleared deleted videos set for fresh page load');
            
            // Suppress Chrome Extension errors
            this.suppressChromeExtensionErrors();
            
            // Setup session management first
            this.setupSessionManagement();
            
            // Check for hard reload scenario
            this.handleHardReload();
            
            // Setup global error handler
            this.setupGlobalErrorHandler();
            
            await this.loadAndApplySettings();
            this.setupEventListeners();
            await this.loadInitialData();
            this.startStatusUpdates();
            
            // Initialize video player system
            this.initializeVideoPlayer();
            
            // بستن همه آکاردئون‌ها به جز اولی
            document.querySelectorAll('.accordion-collapse').forEach((el) => {
                if (el.id !== 'introCollapse') {
                    el.classList.remove('show');
                }
            });
            document.querySelectorAll('.accordion-button').forEach((btn) => {
                if (btn.getAttribute('data-bs-target') !== '#introCollapse') {
                    btn.classList.add('collapsed');
                    btn.setAttribute('aria-expanded', 'false');
                }
            });
            console.log('✅ سیستم دوربین هوشمند راه‌اندازی شد');
        } catch (error) {
            console.error('❌ خطا در راه‌اندازی سیستم:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    // Suppress Chrome Extension errors that don't affect functionality
    suppressChromeExtensionErrors() {
        // Enhanced Chrome extension error suppression
        const chromeExtensionErrors = [
            'Unchecked runtime.lastError',
            'The message port closed before a response was received',
            'Extension context invalidated',
            'Could not establish connection',
            'Receiving end does not exist',
            'Message port closed',
            'runtime.lastError',
            'chrome.runtime.sendMessage',
            'chrome.tabs.sendMessage',
            'chrome.extension.sendMessage',
            'chrome.runtime.onMessage',
            'chrome.tabs.onMessage',
            'chrome.extension.onMessage',
            'chrome.runtime.connect',
            'chrome.tabs.connect',
            'chrome.extension.connect',
            'chrome.runtime.onConnect',
            'chrome.tabs.onConnect',
            'chrome.extension.onConnect',
            'chrome.runtime.onInstalled',
            'chrome.runtime.onStartup',
            'chrome.runtime.onSuspend',
            'chrome.runtime.onUpdateAvailable',
            'chrome.runtime.onBrowserUpdateAvailable',
            'chrome.runtime.onConnectExternal',
            'chrome.runtime.onMessageExternal',
            'chrome.runtime.onRestartRequired',
            'chrome.runtime.onSuspendCanceled',
            'chrome.runtime.onUpdateAvailable',
            'chrome.runtime.onBrowserUpdateAvailable',
            'chrome.runtime.onConnectExternal',
            'chrome.runtime.onMessageExternal',
            'chrome.runtime.onRestartRequired',
            'chrome.runtime.onSuspendCanceled',
            'chrome.runtime.onStartup',
            'chrome.runtime.onInstalled',
            'chrome.runtime.onSuspend',
            'chrome.runtime.onUpdateAvailable',
            'chrome.runtime.onBrowserUpdateAvailable',
            'chrome.runtime.onConnectExternal',
            'chrome.runtime.onMessageExternal',
            'chrome.runtime.onRestartRequired',
            'chrome.runtime.onSuspendCanceled'
        ];

        // Override console.error to filter Chrome extension errors
        const originalConsoleError = console.error;
        console.error = function(...args) {
            const message = args.join(' ');
            const shouldSuppress = chromeExtensionErrors.some(error => 
                message.includes(error)
            );
            
            if (!shouldSuppress) {
                originalConsoleError.apply(console, args);
            }
        };

        // Override console.warn to filter Chrome extension warnings
        const originalConsoleWarn = console.warn;
        console.warn = function(...args) {
            const message = args.join(' ');
            const shouldSuppress = chromeExtensionErrors.some(error => 
                message.includes(error)
            );
            
            if (!shouldSuppress) {
                originalConsoleWarn.apply(console, args);
            }
        };

        // Enhanced error event handler
        window.addEventListener('error', (event) => {
            const message = event.message || '';
            const shouldSuppress = chromeExtensionErrors.some(error => 
                message.includes(error)
            );
            
            if (shouldSuppress) {
                event.preventDefault();
                return false;
            }
        });

        // Enhanced unhandledrejection handler
        window.addEventListener('unhandledrejection', (event) => {
            const message = event.reason?.message || event.reason || '';
            const shouldSuppress = chromeExtensionErrors.some(error => 
                message.includes(error)
            );
            
            if (shouldSuppress) {
                event.preventDefault();
                return false;
            }
        });
    }

    // Handle hard reload scenarios
    handleHardReload() {
        // Check if this is a hard reload (page refresh)
        const isHardReload = !window.performance.getEntriesByType('navigation')[0]?.type || 
                            window.performance.getEntriesByType('navigation')[0]?.type === 'reload';
        
        if (isHardReload) {
            // Set a flag to indicate this is a hard reload
            sessionStorage.setItem('hard_reload', 'true');
            
            // Check if user is admin by making a request to server
            this.checkUserRole();
        }
    }

    setupGlobalErrorHandler() {
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            const message = event.reason?.message || event.reason || 'Unknown error';
            
            // Filter out Chrome extension related errors
            const stack = (event.reason && event.reason.stack) ? String(event.reason.stack) : '';
            if (message.includes('runtime.lastError') || 
                message.includes('message port') || 
                message.includes('chrome-extension') ||
                stack.includes('chrome-extension://') ||
                message.includes('Extension context invalidated')) {
                event.preventDefault();
                return;
            }
            
            console.error('Unhandled promise rejection:', event.reason);
        });

        // Handle global errors
        window.addEventListener('error', (event) => {
            const message = event.message || '';
            
            // Filter out Chrome extension related errors
            if (message.includes('runtime.lastError') || 
                message.includes('message port') || 
                message.includes('chrome-extension') ||
                message.includes('Extension context invalidated')) {
                event.preventDefault();
                return;
            }
        });
    }

    // Check user role and handle session accordingly
    async checkUserRole() {
        try {
            const response = await fetch('/get_user_settings', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest' // Prevent hard reload detection
                },
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.user_role === 'admin') {
                    // Admin user - restore session
                    console.log('Admin user detected - restoring session');
                    sessionStorage.removeItem('hard_reload');
                    
                    // Store admin session info
                    localStorage.setItem('user_role', 'admin');
                    localStorage.setItem('username', data.username);
                    
                    // Restore admin session
                    this.restoreAdminSession();
                } else {
                    // Regular user - force logout on hard reload
                    console.log('Regular user hard reload detected - forcing logout');
                    this.forceLogout();
                }
            } else if (response.status === 401) {
                // Unauthorized - redirect to login
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('Error checking user role:', error);
            // On error, redirect to login for safety
            window.location.href = '/login';
        }
    }

    // Restore admin session after hard reload
    restoreAdminSession() {
        // Set admin-specific flags
        sessionStorage.setItem('admin_session', 'true');
        
        // Show admin notification
        this.showNotification('Admin session restored successfully', 'success');
        
        console.log('Admin session restored after hard reload');
    }

    // Force logout for regular users on hard reload
    forceLogout() {
        // Clear all storage
        localStorage.clear();
        sessionStorage.clear();
        
        // Show notification
        this.showNotification('Session expired. Please login again.', 'warning');
        
        // Redirect to login
        window.location.href = '/login';
    }

    // Enhanced session management
    setupSessionManagement() {
        // Listen for storage events (for multi-tab scenarios)
        window.addEventListener('storage', (e) => {
            if (e.key === 'access_token' && !e.newValue) {
                // Token was cleared in another tab
                this.handleSessionExpired();
            }
        });

        // Listen for beforeunload to save session state
        window.addEventListener('beforeunload', () => {
            if (localStorage.getItem('user_role') === 'admin') {
                sessionStorage.setItem('admin_session_active', 'true');
            }
        });

        // Check for session expiration
        setInterval(() => {
            const expires = localStorage.getItem('token_expires');
            if (expires && Date.now() > parseInt(expires)) {
                this.handleSessionExpired();
            }
        }, 60000); // Check every minute
    }

    // Handle session expiration
    handleSessionExpired() {
        if (localStorage.getItem('user_role') === 'admin') {
            // Admin session expired - show warning but don't force logout
            this.showNotification('Admin session expired. Please refresh the page.', 'warning');
        } else {
            // Regular user session expired - force logout
            this.forceLogout();
        }
    }

    // Load settings from server (preferred) or localStorage, then apply to UI
    async loadAndApplySettings() {
        // Set initialization flag to prevent excessive logging
        this._isInitializing = true;
        
        let settings = null;
        try {
            const res = await fetch('/get_user_settings', { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                if (data.status === 'success' && data.settings) settings = data.settings;
                if (data.language) this.language = data.language;
                // Capture CSRF token for authenticated requests
                if (data.csrf_token) {
                    this.csrfToken = data.csrf_token;
                }
            }
        } catch (error) {
            console.warn('Error loading settings from server:', error);
        }
        if (!settings) {
            settings = {
                theme: 'dark',
                language: localStorage.getItem('language') || 'fa',
                flashSettings: localStorage.getItem('flashSettings') || '{"intensity":50,"enabled":false}',
                servo1: localStorage.getItem('servo1') || 90,
                servo2: localStorage.getItem('servo2') || 90,
                device_mode: localStorage.getItem('device_mode') || 'desktop',
                smart_motion: false,
                smart_tracking: false,
                stream_enabled: false
            };
        }
        
        // Load photo quality from localStorage
        const photoQuality = localStorage.getItem('photoQuality');
        if (photoQuality) {
            settings.photoQuality = parseInt(photoQuality);
        }
        // Always sync language to localStorage
        if (settings.language !== localStorage.getItem('language')) {
            localStorage.setItem('language', settings.language);
        }
        this.language = settings.language || 'fa';
        localStorage.setItem('theme', settings.theme);
        localStorage.setItem('flashSettings', settings.flashSettings);
        localStorage.setItem('servo1', settings.servo1);
        localStorage.setItem('servo2', settings.servo2);
        localStorage.setItem('device_mode', settings.device_mode);
        await this.updateLanguage(this.language);
        this.applySettingsToUI(settings);

        // Re-apply persisted states to devices (stream + servo)
        try {
            if (settings.stream_enabled && !this.isStreaming) {
                await this.toggleStream();
            }
            if (typeof settings.servo1 === 'number' && typeof settings.servo2 === 'number') {
                await this.sendServoCommand();
            }
        } catch (e) {
            console.warn('Apply-to-device on load warning:', e);
        }
        
        // Update UI state once at the end instead of multiple times
        // Only if not already updated recently
        if (!this._lastUIUpdate || Date.now() - this._lastUIUpdate > 1000) {
            this.updateUIStateOnce();
            this._lastUIUpdate = Date.now();
        }
        
        // Clear initialization flag
        this._isInitializing = false;
    }

    // Apply all settings to UI elements
    applySettingsToUI(settings) {
        // Theme
        if (settings.theme === 'dark') document.body.classList.add('dark-mode');
        else document.body.classList.remove('dark-mode');
        const themeIcon = document.getElementById('themeIcon');
        if (themeIcon) {
            themeIcon.classList.remove('fa-moon', 'fa-sun', 'fa-regular', 'fa-solid', 'theme-sun-glow', 'theme-moon-stars', 'theme-rotate');
            Array.from(themeIcon.querySelectorAll('.star')).forEach(e => e.remove());
            if (settings.theme === 'dark') {
                themeIcon.classList.add('fa-sun', 'fa-solid', 'theme-sun-glow', 'theme-rotate');
                themeIcon.style.color = '#fff';
                themeIcon.style.textShadow = '0 0 8px #fff8';
            } else {
                themeIcon.classList.add('fa-moon', 'fa-solid', 'theme-moon-stars', 'theme-rotate');
                themeIcon.style.color = '#fff';
                themeIcon.style.textShadow = '0 0 8px #fff8';
                for (let i = 1; i <= 3; i++) {
                    const star = document.createElement('span');
                    star.className = `star star${i}`;
                    themeIcon.appendChild(star);
                }
            }
        }

        // Flash
        try {
            const flash = JSON.parse(settings.flashSettings);
            const flashIntensity = document.getElementById('flashIntensity');
            const flashToggle = document.getElementById('flashToggle');
            const flashControls = document.getElementById('flashControls');
            if (flashIntensity) flashIntensity.value = flash.intensity;
            if (flashToggle) flashToggle.checked = flash.enabled;
            if (flashControls) flashControls.classList.toggle('active', flash.enabled);
            this.updateFlashIntensityValue(flash.intensity);
        } catch (error) {
            console.warn('Error parsing flash settings:', error);
        }
        // Servo
        const s1 = document.getElementById('servoX');
        const s1Num = document.getElementById('servoXNumber');
        if (s1) s1.value = settings.servo1;
        if (s1Num) s1Num.value = settings.servo1;
        if (document.getElementById('servoXValue')) document.getElementById('servoXValue').textContent = `${settings.servo1}°`;
        const s2 = document.getElementById('servoY');
        const s2Num = document.getElementById('servoYNumber');
        if (s2) s2.value = settings.servo2;
        if (s2Num) s2Num.value = settings.servo2;
        if (document.getElementById('servoYValue')) document.getElementById('servoYValue').textContent = `${settings.servo2}°`;
        // Language icon animation
        const langIcon = document.querySelector('#languageToggle i');
        if (langIcon) {
            langIcon.classList.remove('lang-rotate-rtl', 'lang-rotate-ltr');
            if (settings.language === 'fa') langIcon.classList.add('lang-rotate-rtl');
            else langIcon.classList.add('lang-rotate-ltr');
        }
        // Device mode button UI update
        const btn = document.getElementById('deviceModeToggle');
        if (btn) {
            const mode = settings.device_mode || localStorage.getItem('device_mode') || 'desktop';
            btn.innerHTML = `<i class="fas fa-${mode === 'mobile' ? 'mobile-alt' : 'desktop'} me-2"></i> ${this.getTranslation(mode === 'mobile' ? 'mobileMode' : 'desktopMode')}`;
            btn.classList.toggle('btn-outline-secondary', mode === 'desktop');
            btn.classList.toggle('btn-outline-primary', mode === 'mobile');
        }
        
        // Photo quality slider
        const photoQuality = document.getElementById('photoQuality');
        const qualityValue = document.getElementById('qualityValue');
        if (photoQuality && qualityValue) {
            const savedQuality = settings.photoQuality || localStorage.getItem('photoQuality') || 80;
            photoQuality.value = savedQuality;
            qualityValue.textContent = `${savedQuality}%`;
        }
        
        // Smart features
        if (settings.smart_motion !== undefined || settings.smart_tracking !== undefined) {
            const smartState = {
                motion: settings.smart_motion || false,
                tracking: settings.smart_tracking || false
            };
            setSmartMotionState(smartState);
            updateSmartMotionToggles();
        }
        
        // Stream status
        if (settings.stream_enabled !== undefined) {
            this.streamEnabled = settings.stream_enabled;
            this.isStreaming = settings.stream_enabled;
            // Don't update button here - will be done in updateUIStateOnce
        }
        
        // No need for setTimeout or duplicate button updates
        // All UI updates will be handled by updateUIStateOnce in loadAndApplySettings

        // Auto-apply device-related settings after UI is synced
        try {
            // Apply flash state to device (only if enabled)
            const flash = JSON.parse(settings.flashSettings || '{}');
            if (flash.enabled === true) {
                // Trigger device action without duplicate notifications
                this.toggleFlash(true);
            }
        } catch {}
    }

    // Save all settings to server (and localStorage is always up to date)
    async saveUserSettingsToServer() {
        // Prevent multiple simultaneous saves
        if (this._isSavingSettings) {
            return;
        }
        
        this._isSavingSettings = true;
        
        // Collect current UI settings
        const flashIntensity = document.getElementById('flashIntensity');
        const flashToggle = document.getElementById('flashToggle');
        const servoX = document.getElementById('servoX');
        const servoY = document.getElementById('servoY');
        const photoQuality = document.getElementById('photoQuality');
        const deviceModeToggle = document.getElementById('deviceModeToggle');
        
        const settings = {
            ...this.userSettings,
            language: this.language,
            theme: localStorage.getItem('theme') || 'light',
            flashSettings: JSON.stringify({
                intensity: flashIntensity ? parseInt(flashIntensity.value) : 50,
                enabled: flashToggle ? flashToggle.checked : false
            }),
            servo1: servoX ? parseInt(servoX.value) : 90,
            servo2: servoY ? parseInt(servoY.value) : 90,
            device_mode: localStorage.getItem('device_mode') || 'desktop',
            photoQuality: photoQuality ? parseInt(photoQuality.value) : 80,
            smart_motion: getSmartMotionState().motion || false,
            smart_tracking: getSmartMotionState().tracking || false,
            stream_enabled: this.streamEnabled || false
        };
        
        try {
            const headers = {'Content-Type': 'application/json'};
            if (this.csrfToken) headers['X-CSRF-Token'] = this.csrfToken;
            const response = await fetch('/save_user_settings', {
                method: 'POST',
                body: JSON.stringify(settings),
                headers,
                credentials: 'include'
            });
            
            if (response.ok) {
                console.log('Settings saved successfully');
            } else {
                console.error('Failed to save settings');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
        } finally {
            // Clear the flag after a short delay to prevent rapid successive calls
            setTimeout(() => {
                this._isSavingSettings = false;
            }, 1000);
        }
    }

    async loadSettings() {
        try {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-mode');
            } else {
                document.body.classList.remove('dark-mode');
            }
            // Theme icon
            const themeIcon = document.getElementById('themeIcon');
            if (themeIcon) {
                themeIcon.classList.remove('fa-moon', 'fa-sun', 'fa-regular', 'fa-solid', 'theme-sun-glow', 'theme-moon-stars', 'theme-rotate');
                Array.from(themeIcon.querySelectorAll('.star')).forEach(e => e.remove());
                if (savedTheme === 'dark') {
                    themeIcon.classList.add('fa-sun', 'fa-solid', 'theme-sun-glow', 'theme-rotate');
                    themeIcon.style.color = '#fff';
                    themeIcon.style.textShadow = '0 0 8px #fff8';
                } else {
                    themeIcon.classList.add('fa-moon', 'fa-solid', 'theme-moon-stars', 'theme-rotate');
                    themeIcon.style.color = '#fff';
                    themeIcon.style.textShadow = '0 0 8px #fff8';
                    for (let i = 1; i <= 3; i++) {
                        const star = document.createElement('span');
                        star.className = `star star${i}`;
                        themeIcon.appendChild(star);
                    }
                }
            }
            // Language icon
            const langIcon = document.querySelector('#languageToggle i');
            if (langIcon) {
                langIcon.classList.remove('lang-rotate-rtl', 'lang-rotate-ltr');
                const savedLang = localStorage.getItem('language') || 'fa';
                if (savedLang === 'fa') langIcon.classList.add('lang-rotate-rtl');
                else langIcon.classList.add('lang-rotate-ltr');
            }
            const savedLanguage = localStorage.getItem('language') || 'fa';
            this.language = savedLanguage;
            await this.updateLanguage(savedLanguage);

            const flashSettings = localStorage.getItem('flashSettings');
            if (flashSettings) {
                const { intensity, enabled } = JSON.parse(flashSettings);
                const flashIntensity = document.getElementById('flashIntensity');
                const flashToggle = document.getElementById('flashToggle');
                const flashControls = document.getElementById('flashControls');
                if (flashIntensity) flashIntensity.value = intensity;
                if (flashToggle) flashToggle.checked = enabled;
                if (flashControls) flashControls.classList.toggle('active', enabled);
                this.updateFlashIntensityValue(intensity);
            }

            const servo1 = localStorage.getItem('servo1');
            const servo2 = localStorage.getItem('servo2');
            if (servo1 !== null) {
                const s1 = document.getElementById('servoX');
                const s1Num = document.getElementById('servoXNumber');
                if (s1) s1.value = servo1;
                if (s1Num) s1Num.value = servo1;
                if (document.getElementById('servoXValue')) document.getElementById('servoXValue').textContent = `${servo1}°`;
            }
            if (servo2 !== null) {
                const s2 = document.getElementById('servoY');
                const s2Num = document.getElementById('servoYNumber');
                if (s2) s2.value = servo2;
                if (s2Num) s2Num.value = servo2;
                if (document.getElementById('servoYValue')) document.getElementById('servoYValue').textContent = `${servo2}°`;
            }
        } catch (error) {
            console.error('خطا در بارگذاری تنظیمات:', error);
        }
    }

    getTranslation(key, fallback = '') {
        return (this.translations && this.translations[key]) || fallback || key;
    }

    getAuthToken() {
        // Try to get token from localStorage first
        let token = localStorage.getItem('access_token');
        console.log('[DEBUG] Token from localStorage:', token ? 'Found' : 'Not found');
        
        // If not in localStorage, try to get from cookies
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'access_token' || name === 'token') {
                    token = value;
                    console.log('[DEBUG] Token found in cookie:', name);
                    break;
                }
            }
        }
        
        // If still no token, try to get from sessionStorage
        if (!token) {
            token = sessionStorage.getItem('access_token');
            console.log('[DEBUG] Token from sessionStorage:', token ? 'Found' : 'Not found');
        }
        
        // Also check for any cookie that might contain 'token' in the name
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                if (cookie.includes('token') || cookie.includes('auth')) {
                    console.log('[DEBUG] Found potential auth cookie:', cookie);
                    const [name, value] = cookie.trim().split('=');
                    if (value && value.length > 10) { // Basic validation
                        token = value;
                        console.log('[DEBUG] Using token from cookie:', name);
                        break;
                    }
                }
            }
        }
        
        console.log('[DEBUG] Final token result:', token ? 'Token found' : 'No token found');
        return token;
    }

    async isAuthenticated() {
        const token = this.getAuthToken();
        if (!token) {
            console.log('[DEBUG] No token found for authentication check');
            // Fallback to server check
            return await this.checkServerAuth();
        }
        
        console.log('[DEBUG] Checking authentication for token length:', token.length);
        
        // Check if token is expired (basic check)
        try {
            // Handle different token formats
            let payload;
            if (token.includes('.')) {
                // JWT token format
                const parts = token.split('.');
                if (parts.length !== 3) {
                    console.warn('[DEBUG] Invalid JWT token format, parts:', parts.length);
                    return await this.checkServerAuth();
                }
                payload = JSON.parse(atob(parts[1]));
            } else {
                // Simple token format
                console.log('[DEBUG] Non-JWT token format detected, treating as valid');
                return true;
            }
            
            const now = Math.floor(Date.now() / 1000);
            const isExpired = payload.exp && payload.exp < now;
            
            console.log('[DEBUG] Token expiration check:', {
                tokenExp: payload.exp,
                currentTime: now,
                isExpired: isExpired
            });
            
            if (isExpired) {
                console.log('[DEBUG] Token expired, trying server auth check');
                return await this.checkServerAuth();
            }
            
            return true;
        } catch (e) {
            console.warn('[DEBUG] Error parsing token:', e);
            console.log('[DEBUG] Token that caused error:', token.substring(0, 50) + '...');
            // Fallback to server check
            return await this.checkServerAuth();
        }
    }

    async refreshAuthToken() {
        try {
            const response = await fetch('/refresh_token', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.access_token) {
                    localStorage.setItem('access_token', data.access_token);
                    console.log('[DEBUG] Authentication token refreshed successfully');
                    return true;
                }
            }
        } catch (error) {
            console.error('[DEBUG] Error refreshing token:', error);
        }
        return false;
    }

    async checkServerAuth() {
        try {
            // Try to get user settings as a simple auth check
            const response = await fetch('/get_user_settings', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (response.ok) {
                console.log('[DEBUG] Server authentication check successful');
                return true;
            } else if (response.status === 401) {
                console.log('[DEBUG] Server authentication check failed: Unauthorized');
                return false;
            } else {
                console.log('[DEBUG] Server authentication check status:', response.status);
                return false;
            }
        } catch (error) {
            console.error('[DEBUG] Server authentication check error:', error);
            return false;
        }
    }

    setupEventListeners() {
        const elements = {
            toggleStreamBtn: document.getElementById('toggleStreamBtn'),
            deviceModeToggle: document.getElementById('deviceModeToggle'),
            capturePhotoBtn: document.getElementById('capturePhotoBtn'),
            photoQuality: document.getElementById('photoQuality'),
            flashIntensity: document.getElementById('flashIntensity'),
            flashToggle: document.getElementById('flashToggle'),
            sendServoBtn: document.getElementById('sendServoBtn'),
            resetServoBtn: document.getElementById('resetServoBtn'),
            loadMoreBtn: document.getElementById('loadMoreBtn'),
            loadMoreVideosBtn: document.getElementById('loadMoreVideosBtn'),
            refreshLogsBtn: document.getElementById('refreshLogsBtn'),
            showAllLogsBtn: document.getElementById('showAllLogsBtn'),
            themeToggle: document.getElementById('themeToggle'),
            languageToggle: document.getElementById('languageToggle'),
            logoutBtn: document.getElementById('logoutBtn'),
            menuToggle: document.querySelector('.menu-toggle'),
            footerThemeBtn: document.getElementById('footerThemeBtn'),
            footerLangBtn: document.getElementById('footerLangBtn'),
            profileHeaderBtn: document.getElementById('profileHeaderBtn')
        };

        // Helper to safely replace and rebind event listeners
        function replaceAndBind(btn, handler) {
            if (btn && btn.parentNode) {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
                newBtn.addEventListener('click', (e) => { e.preventDefault(); handler(); });
            }
        }
        
        // فقط event listener های ضروری را در ابتدا تنظیم کن
        replaceAndBind(elements.themeToggle, () => this.toggleTheme());
        replaceAndBind(elements.languageToggle, () => this.toggleLanguage());
        replaceAndBind(elements.footerThemeBtn, () => this.toggleTheme());
        replaceAndBind(elements.footerLangBtn, () => this.toggleLanguage());
        
        // Event listener های مربوط به استریم و دوربین فقط در صورت نیاز
        if (elements.toggleStreamBtn) {
            elements.toggleStreamBtn.addEventListener('click', () => this.toggleStream());
        }
        
        if (elements.deviceModeToggle) {
            elements.deviceModeToggle.addEventListener('click', () => this.toggleDeviceMode());
        }
        
        // Event listener های مربوط به عکس‌برداری
        if (elements.capturePhotoBtn) {
            elements.capturePhotoBtn.addEventListener('click', () => this.capturePhoto());
        }
        
        // Event listener های تنظیمات
        if (elements.photoQuality) {
            elements.photoQuality.addEventListener('input', (e) => {
                const val = e.target.value;
                const qEl = document.getElementById('qualityValue');
                if (qEl) qEl.textContent = `${val}%`;
                localStorage.setItem('photoQuality', val);
                // Save to server
                this.saveUserSettingsToServer();
            });
        }
        
        if (elements.flashIntensity) {
            elements.flashIntensity.addEventListener('input', (e) => {
                const val = e.target.value;
                const fiEl = document.getElementById('flashIntensityValue');
                if (fiEl) fiEl.textContent = `${val}%`;
                // Update localStorage
                let flashSettings = localStorage.getItem('flashSettings');
                try {
                    flashSettings = JSON.parse(flashSettings || '{}');
                } catch { flashSettings = {}; }
                flashSettings.intensity = val;
                localStorage.setItem('flashSettings', JSON.stringify(flashSettings));
                // Save to server
                this.saveUserSettingsToServer();
            });
        }
        
        if (elements.flashToggle) {
            elements.flashToggle.addEventListener('change', (e) => {
                this.toggleFlash(e.target.checked);
                // Save to server
                this.saveUserSettingsToServer();
            });
        }
        
        // Event listener های سروو - فقط در صورت نیاز
        if (elements.sendServoBtn) {
            elements.sendServoBtn.addEventListener('click', () => this.sendServoCommand());
        }
        
        if (elements.resetServoBtn) {
            elements.resetServoBtn.addEventListener('click', () => this.resetServo());
        }
        
        // Event listener های گالری
        if (elements.loadMoreBtn) {
            elements.loadMoreBtn.addEventListener('click', () => this.loadMorePhotos());
        }
        
        if (elements.loadMoreVideosBtn) {
            elements.loadMoreVideosBtn.addEventListener('click', () => this.loadMoreVideos());
        }
        
        // Event listener های لاگ
        if (elements.refreshLogsBtn) {
            elements.refreshLogsBtn.addEventListener('click', () => this.loadLogs());
        }
        
        if (elements.showAllLogsBtn) {
            elements.showAllLogsBtn.addEventListener('click', () => this.showAllLogs());
        }
        
        if (elements.logoutBtn) {
            elements.logoutBtn.addEventListener('click', () => this.logout());
        }
        
        if (elements.menuToggle) {
            elements.menuToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const nav = document.querySelector('.header-nav');
                nav.classList.toggle('active');
            });
            // بستن منو با کلیک بیرون
            document.addEventListener('click', (e) => {
                const nav = document.querySelector('.header-nav');
                if (nav.classList.contains('active') && !nav.contains(e.target) && !elements.menuToggle.contains(e.target)) {
                    nav.classList.remove('active');
                }
            });
            // بستن منو با کلیک روی آیتم منو
            document.querySelectorAll('.header-nav a').forEach(link => {
                link.addEventListener('click', () => {
                    const nav = document.querySelector('.header-nav');
                    nav.classList.remove('active');
                });
            });
        }

        // Event listener های گالری
        document.querySelectorAll('.gallery-item').forEach(item => {
            item.addEventListener('click', () => {
                const url = item.dataset.url;
                const timestamp = item.dataset.timestamp;
                const isVideo = item.querySelector('video') !== null;
                const filename = item.dataset.filename;
                const weekday = item.dataset.weekday || '';
                this.showGalleryModal(url, timestamp, isVideo, filename, weekday);
            });
        });

        // تنظیم کنترل‌های سروو و آکاردئون
        this.setupServoControls();
        this.setupAccordionEvents();
        
        // Setup profile functionality
        this.setupProfileFunctionality();
    }

    setupProfileFunctionality() {
        // Profile header button
        const profileHeaderBtn = document.getElementById('profileHeaderBtn');
        if (profileHeaderBtn) {
            profileHeaderBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.showProfileModal();
            });
        }

        // Footer profile button
        const footerProfileBtn = document.getElementById('footerProfileBtn');
        if (footerProfileBtn) {
            footerProfileBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.showMobileProfilePage();
            });
        }

        // Setup profile modal buttons
        this.setupProfileModalButtons();
    }

    setupProfileModalButtons() {
        // Profile modal buttons
        const profileSettingsBtn = document.getElementById('profileSettingsBtn');
        const profileHelpBtn = document.getElementById('profileHelpBtn');
        const profileAboutBtn = document.getElementById('profileAboutBtn');
        const profileLogoutBtn = document.getElementById('profileLogoutBtn');

        // Mobile profile buttons
        const mobileProfileSettingsBtn = document.getElementById('mobileProfileSettingsBtn');
        const mobileProfileHelpBtn = document.getElementById('mobileProfileHelpBtn');
        const mobileProfileAboutBtn = document.getElementById('mobileProfileAboutBtn');
        const mobileProfileLogoutBtn = document.getElementById('mobileProfileLogoutBtn');

        if (profileSettingsBtn) {
            profileSettingsBtn.addEventListener('click', () => this.showNotification('profileSettings', 'info'));
        }
        if (profileHelpBtn) {
            profileHelpBtn.addEventListener('click', () => this.showNotification('profileHelp', 'info'));
        }
        if (profileAboutBtn) {
            profileAboutBtn.addEventListener('click', () => this.showNotification('profileAbout', 'info'));
        }
        if (profileLogoutBtn) {
            profileLogoutBtn.addEventListener('click', () => this.logout());
        }

        if (mobileProfileSettingsBtn) {
            mobileProfileSettingsBtn.addEventListener('click', () => this.showNotification('profileSettings', 'info'));
        }
        if (mobileProfileHelpBtn) {
            mobileProfileHelpBtn.addEventListener('click', () => this.showNotification('profileHelp', 'info'));
        }
        if (mobileProfileAboutBtn) {
            mobileProfileAboutBtn.addEventListener('click', () => this.showNotification('profileAbout', 'info'));
        }
        if (mobileProfileLogoutBtn) {
            mobileProfileLogoutBtn.addEventListener('click', () => this.logout());
        }
    }

    async showProfileModal() {
        try {
            const modalElement = document.getElementById('profileModal');
            if (modalElement && typeof bootstrap !== 'undefined') {
                // Check if modal is already shown
                if (modalElement.classList.contains('show')) {
                    console.log('Modal is already shown');
                    return;
                }
                
                // Load profile data from server
                await this.loadProfileData();
                
                // Create new modal instance with proper options
                const profileModal = new bootstrap.Modal(modalElement, {
                    backdrop: true,
                    keyboard: true,
                    focus: true
                });
                
                // Show modal
                profileModal.show();
                
                // Prevent modal from auto-hiding
                modalElement.addEventListener('hidden.bs.modal', (e) => {
                    console.log('Modal hidden event triggered');
                }, { once: true });
                
                console.log('Profile modal shown successfully');
            } else {
                console.warn('Bootstrap or modal element not available');
                // Fallback: show modal manually
                if (modalElement) {
                    // Load profile data from server
                    await this.loadProfileData();
                    
                    modalElement.style.display = 'block';
                    modalElement.classList.add('show');
                    document.body.classList.add('modal-open');
                    
                    // Add backdrop
                    const backdrop = document.createElement('div');
                    backdrop.className = 'modal-backdrop fade show';
                    backdrop.id = 'profileModalBackdrop';
                    document.body.appendChild(backdrop);
                    
                    console.log('Modal shown with fallback method');
                }
            }
        } catch (error) {
            console.error('Error showing profile modal:', error);
        }
    }

    async showMobileProfilePage() {
        const mobileProfilePage = document.getElementById('mobileProfilePage');
        if (mobileProfilePage) {
            // Load profile data from server
            await this.loadProfileData();
            mobileProfilePage.style.display = 'block';
        }
    }

    hideMobileProfilePage() {
        const mobileProfilePage = document.getElementById('mobileProfilePage');
        if (mobileProfilePage) {
            mobileProfilePage.style.display = 'none';
        }
    }

    hideProfileModal() {
        try {
            const modalElement = document.getElementById('profileModal');
            if (modalElement && typeof bootstrap !== 'undefined') {
                const profileModal = bootstrap.Modal.getInstance(modalElement);
                if (profileModal) {
                    profileModal.hide();
                }
            } else {
                // Fallback: hide modal manually
                if (modalElement) {
                    modalElement.style.display = 'none';
                    modalElement.classList.remove('show');
                    document.body.classList.remove('modal-open');
                    
                    // Remove backdrop
                    const backdrop = document.getElementById('profileModalBackdrop');
                    if (backdrop) {
                        backdrop.remove();
                    }
                }
            }
        } catch (error) {
            console.error('Error hiding profile modal:', error);
        }
    }

    async loadProfileData() {
        try {
            const response = await fetch('/api/profile', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                    'Content-Type': 'application/json'
                },
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.profile) {
                    this.updateProfileUI(data.profile);
                } else {
                    console.error('Invalid profile data received:', data);
                }
            } else {
                console.error('Failed to load profile data:', response.status);
            }
        } catch (error) {
            console.error('Error loading profile data:', error);
        }
    }

    updateProfileUI(profileData) {
        // Update desktop profile modal
        const profileUsername = document.getElementById('profileUsername');
        const profileRole = document.getElementById('profileRole');
        
        if (profileUsername) {
            profileUsername.textContent = profileData.username;
        }
        
        if (profileRole) {
            const roleText = profileData.role === 'admin' ? 'مدیر سیستم' : 'کاربر';
            profileRole.textContent = roleText;
        }

        // Update mobile profile page
        const mobileProfileUsername = document.getElementById('mobileProfileUsername');
        const mobileProfileRole = document.getElementById('mobileProfileRole');
        
        if (mobileProfileUsername) {
            mobileProfileUsername.textContent = profileData.username;
        }
        
        if (mobileProfileRole) {
            const roleText = profileData.role === 'admin' ? 'مدیر سیستم' : 'کاربر';
            mobileProfileRole.textContent = roleText;
        }

        console.log('Profile UI updated with data:', profileData);
    }

    setupServoControls() {
        const servoX = document.getElementById('servoX');
        const servoXNumber = document.getElementById('servoXNumber');
        const servoY = document.getElementById('servoY');
        const servoYNumber = document.getElementById('servoYNumber');

        // Helper to send only on release
        const sendFinalServo = () => {
            this.saveUserSettingsToServer();
            this.sendServoCommand();
        };

        if (servoX && servoXNumber) {
            servoX.addEventListener('input', () => {
                const val = servoX.value;
                servoXNumber.value = val;
                const sxv = document.getElementById('servoXValue');
                if (sxv) sxv.textContent = `${val}°`;
                localStorage.setItem('servo1', val);
            });
            servoX.addEventListener('change', sendFinalServo);
            servoX.addEventListener('mouseup', sendFinalServo);
            servoX.addEventListener('touchend', sendFinalServo);
            servoXNumber.addEventListener('input', () => {
                let val = Math.max(0, Math.min(180, parseInt(servoXNumber.value) || 0));
                servoX.value = val;
                servoXNumber.value = val;
                const sxv2 = document.getElementById('servoXValue');
                if (sxv2) sxv2.textContent = `${val}°`;
                localStorage.setItem('servo1', val);
            });
            servoXNumber.addEventListener('change', sendFinalServo);
            servoXNumber.addEventListener('mouseup', sendFinalServo);
            servoXNumber.addEventListener('touchend', sendFinalServo);
        }

        if (servoY && servoYNumber) {
            servoY.addEventListener('input', () => {
                const val = servoY.value;
                servoYNumber.value = val;
                const syv = document.getElementById('servoYValue');
                if (syv) syv.textContent = `${val}°`;
                localStorage.setItem('servo2', val);
            });
            servoY.addEventListener('change', sendFinalServo);
            servoY.addEventListener('mouseup', sendFinalServo);
            servoY.addEventListener('touchend', sendFinalServo);
            servoYNumber.addEventListener('input', () => {
                let val = Math.max(0, Math.min(180, parseInt(servoYNumber.value) || 0));
                servoY.value = val;
                servoYNumber.value = val;
                const syv2 = document.getElementById('servoYValue');
                if (syv2) syv2.textContent = `${val}°`;
                localStorage.setItem('servo2', val);
            });
            servoYNumber.addEventListener('change', sendFinalServo);
            servoYNumber.addEventListener('mouseup', sendFinalServo);
            servoYNumber.addEventListener('touchend', sendFinalServo);
        }
    }

    setupAccordionEvents() {
        const galleryCollapse = document.getElementById('galleryCollapse');
        const videosCollapse = document.getElementById('videosCollapse');
        const logsCollapse = document.getElementById('logsCollapse');

        if (galleryCollapse) {
            galleryCollapse.addEventListener('show.bs.collapse', () => {
                if (this.currentPage === 0) this.loadGallery();
            });
        }

        if (videosCollapse) {
            videosCollapse.addEventListener('show.bs.collapse', () => {
                if (this.currentVideoPage === 0) {
                    this.loadVideos();
                } else {
                    // Optimize existing videos for faster previews
                    this.optimizeExistingVideos();
                }
            });
        }

        if (logsCollapse) {
            // جلوگیری از ثبت چندباره رویداد
            if (!logsCollapse._logEventSet) {
                logsCollapse.addEventListener('show.bs.collapse', () => this.loadLogs());
                logsCollapse._logEventSet = true;
            }
        }

        // Handle scrollbar visibility to prevent layout shift when accordions toggle
        const accordionRoot = document.getElementById('mainAccordion') || document;
        if (accordionRoot && !accordionRoot._scrollbarEventsBound) {
            const onAnyShow = () => {
                document.body.classList.add('scrollbar-hidden');
            };
            const onAnyHide = () => {
                // Delay to allow collapse animation to finish smoothly
                setTimeout(() => {
                    // If no accordion content is currently open, or even if open, we keep class until next frame to avoid flicker
                    document.body.classList.remove('scrollbar-hidden');
                }, 200);
            };

            document.querySelectorAll('.accordion-collapse').forEach((el) => {
                el.addEventListener('show.bs.collapse', onAnyShow);
                el.addEventListener('hidden.bs.collapse', onAnyHide);
            });

            accordionRoot._scrollbarEventsBound = true;
        }
    }

    // Optimize existing videos for faster previews
    optimizeExistingVideos() {
        try {
            const videosContainer = document.getElementById('videosContainer');
            if (!videosContainer) return;
            
            const videoElements = videosContainer.querySelectorAll('video');
            videoElements.forEach(videoElement => {
                if (videoElement && !videoElement.src) {
                    // Load videos that haven't been loaded yet
                    const dataSrc = videoElement.dataset.src;
                    if (dataSrc) {
                        this.loadVideoPreview(videoElement, 'existing');
                    }
                }
            });
        } catch (error) {
            console.warn('Error optimizing existing videos:', error);
        }
    }

    async setupWebSocket() {
        if (window.isReloading) return;
        
        // Check if user is authenticated before attempting connection
        const isAuth = await this.isAuthenticated();
        if (!isAuth) {
            console.warn('[DEBUG] User not authenticated, cannot establish WebSocket connection');
            this.showNotification('کاربر احراز هویت نشده است', 'warning');
            return;
        }
        
        try {
            // Close existing connection if any
            if (this.websocket) {
                this.websocket.close();
                this.websocket = null;
            }
            
            // Clear any existing reconnection timer
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }

            this.websocket = null;

            // Get current protocol and host
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            
            // Use video WebSocket endpoint for streaming
            const wsUrl = this.isStreaming ? 
                `${protocol}//${host}/ws/video` : 
                `${protocol}//${host}/ws`;

            console.log(`[DEBUG] Attempting WebSocket connection to: ${wsUrl}`);

            // Reset cooldown for fresh connection attempts
            this.lastConnectionAttempt = Date.now();

            // Get authentication token from cookies
            const token = this.getAuthToken();
            if (!token) {
                console.error('[DEBUG] No authentication token found, cannot establish WebSocket connection');
                this.showNotification('توکن احراز هویت یافت نشد', 'error');
                return;
            }

            // Create WebSocket with authentication headers
            // Note: WebSocket doesn't support custom headers in the constructor
            // We'll need to send the token as the first message after connection
            this.websocket = new WebSocket(wsUrl);
            
            // Set binary type for video frames
            if (this.isStreaming) {
                this.websocket.binaryType = 'arraybuffer';
                console.log('[DEBUG] WebSocket binary type set to arraybuffer for streaming');
            }
            
            // Set connection timeout
            const connectionTimeout = setTimeout(() => {
                if (this.websocket && this.websocket.readyState !== WebSocket.OPEN) {
                    console.warn('[DEBUG] WebSocket connection timeout');
                    this.websocket.close();
                    this.scheduleReconnect();
                }
            }, 10000); // 10 second timeout

            this.websocket.onopen = (event) => {
                if (window.isReloading) return;
                clearTimeout(connectionTimeout);
                
                console.log('[DEBUG] WebSocket connected successfully, sending authentication...');
                
                // Send authentication token immediately after connection
                this.websocket.send(JSON.stringify({
                    type: 'authenticate',
                    token: token,
                    timestamp: Date.now()
                }));
                
                // Don't set isConnected yet - wait for authentication response
            };
            
            this.websocket.onmessage = async (event) => {
                if (window.isReloading) return;
                
                // Handle binary data for video frames
                if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
                    console.log('[DEBUG] Received video frame data:', event.data.byteLength || event.data.size, 'bytes');
                    this.handleVideoFrame(event.data);
                    return;
                }
                
                // Handle text messages
                try {
                    const data = JSON.parse(event.data);
                    console.log('[DEBUG] Received WebSocket message:', data.type, data);
                    
                    // Handle authentication response first
                    if (data.type === 'authenticated') {
                        console.log('[DEBUG] WebSocket authentication successful');
                        this.isConnected = true;
                        this.systemStatus.websocket = 'connected';
                        this.updateConnectionStatus(true);
                        this.updateStatusModal();
                        this.connectionErrorShown = false;
                        this.retryCount = 0; // Reset retry count on successful connection
                        
                        // Send initial status request
                        this.websocket.send(JSON.stringify({
                            type: 'get_status',
                            timestamp: Date.now()
                        }));
                        
                        // Start ping-pong mechanism
                        this.startPingPong();
                        
                        // If this is a streaming connection, send stream start request
                        if (this.isStreaming) {
                            console.log('[DEBUG] Sending stream start request');
                            this.websocket.send(JSON.stringify({
                                type: 'start_stream',
                                timestamp: Date.now()
                            }));
                        }
                        return;
                    }
                    
                    // Handle authentication failure
                    if (data.type === 'auth_failed') {
                        console.error('[DEBUG] WebSocket authentication failed:', data.message);
                        this.websocket.close(4001, 'Authentication failed');
                        this.showNotification('احراز هویت WebSocket ناموفق بود', 'error');
                        
                        // Try to refresh token if authentication failed
                        if (data.message && data.message.includes('Invalid token')) {
                            console.log('[DEBUG] Attempting to refresh authentication token...');
                            const refreshed = await this.refreshAuthToken();
                            if (refreshed) {
                                console.log('[DEBUG] Token refreshed, retrying WebSocket connection...');
                                setTimeout(async () => await this.setupWebSocket(), 1000);
                            } else {
                                console.warn('[DEBUG] Token refresh failed, redirecting to login...');
                                setTimeout(() => {
                                    window.location.href = '/login';
                                }, 2000);
                            }
                        }
                        return;
                    }
                    
                    // Handle specific message types
                    if (data.type === 'stream_started') {
                        console.log('[DEBUG] Stream started successfully');
                        this.isStreaming = true;
                        this.updateStreamButton();
                    } else if (data.type === 'stream_error') {
                        console.error('[DEBUG] Stream error:', data.message);
                        this.showNotification(data.message || 'خطا در شروع استریم', 'error');
                    } else {
                        this.handleWebSocketMessage(data);
                    }
                } catch (error) {
                    console.error('[DEBUG] Error parsing WebSocket message:', error);
                }
            };
            
            this.websocket.onerror = (event) => {
                if (window.isReloading) return;
                clearTimeout(connectionTimeout);
                
                console.error('[DEBUG] WebSocket error:', event);
                console.error('[DEBUG] WebSocket error details:', {
                    type: event.type,
                    target: event.target,
                    isTrusted: event.isTrusted,
                    readyState: this.websocket?.readyState
                });
                
                // Only show error if connection is not established
                if (this.websocket && this.websocket.readyState !== WebSocket.OPEN) {
                    this.systemStatus.websocket = 'disconnected';
                    this.updateConnectionStatus(false);
                    this.updateStatusModal();
                    
                    // Don't show error notification immediately, wait for onclose
                    console.log('[DEBUG] WebSocket error occurred, waiting for close event');
                }
                
                // Check if this might be an authentication issue
                if (event.target && event.target.readyState === WebSocket.CLOSED) {
                    console.warn('[DEBUG] WebSocket closed during error, may be authentication issue');
                }
            };
            
            this.websocket.onclose = (event) => {
                if (window.isReloading) return;
                clearTimeout(connectionTimeout);
                
                console.log(`[DEBUG] WebSocket closed - code: ${event.code}, reason: ${event.reason}, wasClean: ${event.wasClean}`);
                
                // Stop ping-pong mechanism
                this.stopPingPong();
                
                // Update connection state
                this.isConnected = false;
                
                // Handle different close codes
                if (event.code === 1000 || event.code === 1001) {
                    // Normal closure or going away - don't reconnect
                    console.log('[DEBUG] WebSocket closed normally, not reconnecting');
                } else if (event.code === 1006) {
                    // Abnormal closure - try to reconnect
                    console.warn('[DEBUG] WebSocket abnormal closure, attempting reconnect');
                    
                    // Show error notification only once
                    if (!this.connectionErrorShown) {
                        this.showNotification(this.getTranslation('connectionError'), 'error');
                        this.connectionErrorShown = true;
                    }
                    
                    this.scheduleReconnect();
                } else {
                    console.warn(`[DEBUG] WebSocket closed with code ${event.code}: ${event.reason}`);
                    // Only reconnect for unexpected closures
                    if (event.code !== 1000 && event.code !== 1001) {
                        this.scheduleReconnect();
                    }
                }
                
                // Only update state if this is the current WebSocket connection
                if (this.websocket && this.isStreaming) {
                    this.isStreaming = false;
                    this.updateStreamButton();
                    
                    if (event.code !== 1000 && event.code !== 1001) { // Not a normal closure
                        console.warn(`[DEBUG] WebSocket closed unexpectedly - code: ${event.code}, reason: ${event.reason}`);
                        this.showNotification('اتصال استریم قطع شد', 'warning');
                    }
                }
                
                // Update system status
                this.systemStatus.websocket = 'disconnected';
                this.updateConnectionStatus(false);
                this.updateStatusModal();
                
                // Clear ESP32CAM status cache when WebSocket closes
                this._esp32camStatusCache = null;
                
                // Ensure streaming state is properly reset
                this.isStreaming = false;
                this.updateStreamButton();
            };
            
        } catch (error) {
            if (window.isReloading) return;
            clearTimeout(connectionTimeout);
            console.error('خطا در راه‌اندازی WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    // Separate method for setting up WebSocket event handlers
    setupWebSocketEventHandlers() {
        if (!this.websocket) return;
        
        // Event handlers are now set up in the main setupWebSocket method
        // This method is kept for compatibility but the actual handlers are in setupWebSocket
        console.log('[DEBUG] WebSocket event handlers setup completed');
    }

    scheduleReconnect() {
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            // Use exponential backoff with jitter to prevent thundering herd
            const baseDelay = this.retryDelay;
            const maxDelay = 30000; // Max 30 seconds
            const delay = Math.min(baseDelay * Math.pow(2, this.retryCount - 1), maxDelay);
            // Add jitter (±20%) to prevent multiple clients reconnecting simultaneously
            const jitter = delay * 0.2 * (Math.random() - 0.5);
            const finalDelay = Math.max(1000, delay + jitter); // Minimum 1 second
            
            console.log(`[DEBUG] Scheduling WebSocket reconnection in ${Math.round(finalDelay)}ms (attempt ${this.retryCount}/${this.maxRetries})`);
            
            // Clear any existing reconnection timer
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
            }
            
            this.reconnectTimer = setTimeout(() => {
                if (!this.isConnected && !window.isReloading) {
                    console.log('[DEBUG] Attempting reconnection...');
                    this.setupWebSocket().catch(err => console.error('[DEBUG] Reconnection error:', err));
                }
            }, finalDelay);
        } else {
            console.error('[DEBUG] Maximum WebSocket reconnection attempts reached');
            
            // Reset retry count after a longer delay and try again
            setTimeout(() => {
                console.log('[DEBUG] Resetting retry count and attempting reconnection...');
                this.retryCount = 0;
                this.connectionErrorShown = false; // Reset error notification flag
                this.scheduleReconnect();
            }, 60000); // Wait 1 minute before allowing more retries
        }
    }

    // Ping-Pong mechanism to keep connection alive
    startPingPong() {
        // Clear any existing ping interval
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
        }
        
        // Send ping every 30 seconds
        this.pingInterval = setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: Date.now()
                }));
                console.log('[DEBUG] Ping sent');
            }
        }, 30000); // 30 seconds
        
        // Check for pong responses every 10 seconds
        this.pongCheckInterval = setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                const now = Date.now();
                const lastPong = this.lastPongTime || 0;
                
                // If no pong received in last 60 seconds, reconnect
                if (now - lastPong > 60000) {
                    console.warn('[DEBUG] No pong received, reconnecting...');
                    this.websocket.close();
                    this.scheduleReconnect();
                }
            }
        }, 10000); // 10 seconds
    }

    stopPingPong() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.pongCheckInterval) {
            clearInterval(this.pongCheckInterval);
            this.pongCheckInterval = null;
        }
    }

    handleWebSocketMessage(data) {
        try {
            // بررسی اعتبار داده
            if (!data || typeof data !== 'object') {
                console.warn('Invalid WebSocket message received:', data);
                return;
            }
            
            if (data.type === 'status') {
                Object.keys(data).forEach(key => {
                    if (key !== 'type') this.systemStatus[key] = data[key];
                });
                this.updateStatusModal && this.updateStatusModal();
                updateStatusPage && updateStatusPage();
                return;
            }
            
            switch (data.type) {
                case 'frame':
                    if (data.data && data.resolution) {
                        this.updateStreamFrame(data.data, data.resolution);
                    } else {
                        console.warn('Invalid frame data received:', data);
                    }
                    break;
                case 'photo_captured':
                    this.handlePhotoCaptured(data);
                    break;
                case 'video_created':
                    this.handleVideoCreated(data);
                    break;
                case 'video_deleted':
                    this.handleVideoDeleted(data);
                    break;
                case 'photo_deleted':
                    this.handlePhotoDeleted(data);
                    break;
                case 'motion_detected':
                    this.showNotification(this.getTranslation('motionDetected'), 'warning');
                    break;
                case 'command_response':
                    this.handleCommandResponse(data);
                    break;
                case 'critical_error':
                    this.handleCriticalError(data);
                    break;
                case 'error':
                    this.showNotification(data.message || 'Unknown error', 'error');
                    break;
                case 'pong':
                    // Handle pong response
                    this.lastPongTime = Date.now();
                    console.log('[DEBUG] Pong received');
                    break;
                case 'ping':
                    // Send pong response
                    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                        this.websocket.send(JSON.stringify({type: 'pong'}));
                        console.log('[DEBUG] Pong sent in response to ping');
                    }
                    break;
                default:
                    console.log('پیام WebSocket ناشناخته:', data);
            }
        } catch (error) {
            console.error('خطا در پردازش پیام WebSocket:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
            
            // Log detailed error information
            if (error.stack) {
                console.error('Error stack:', error.stack);
            }
        }
    }

    // Handle video deleted WebSocket message
    handleVideoDeleted(data) {
        try {
            const filename = data.filename;
            if (!filename) {
                console.warn('Video deleted message missing filename:', data);
                return;
            }
            
            console.log(`Video deleted via WebSocket: ${filename}`);
            
            // Remove video from gallery immediately
            this.removeVideoFromGallery(filename);
            
            // Close any open modals that might be showing this video
            this.closeModalsForVideo(filename);
            
            // Remove from deleting set if it was there
            this.deletingVideos.delete(filename);
            
            // Re-enable delete buttons
            this.reEnableDeleteButtons(filename);
            
            // Refresh gallery to update pagination
            this.currentVideoPage = 0;
            this.loadVideos();
            
            // Show success notification
            this.showNotification('ویدیو با موفقیت حذف شد', 'success');
            
        } catch (error) {
            console.error('Error handling video deleted message:', error);
        }
    }

    // Handle photo deleted WebSocket message
    handlePhotoDeleted(data) {
        try {
            const filename = data.filename;
            if (!filename) {
                console.warn('Photo deleted message missing filename:', data);
                return;
            }
            
            console.log(`Photo deleted via WebSocket: ${filename}`);
            
                    // Remove from deleting set if it was there
        if (this.deletingPhotos) {
            this.deletingPhotos.delete(filename);
        }
        
        // Re-enable delete buttons
        this.reEnablePhotoDeleteButtons(filename);
        
        // Remove photo from gallery immediately
        this.removePhotoFromGallery(filename);
            
            // Close any open modals that might be showing this photo
            this.closeModalsForPhoto(filename);
            
            // Refresh gallery to update pagination
            this.currentPage = 0;
            this.loadGallery();
            
            // Show success notification
            this.showNotification('تصویر با موفقیت حذف شد', 'success');
            
        } catch (error) {
            console.error('Error handling photo deleted message:', error);
        }
    }

    // Clean up video player state before deletion
    async cleanupVideoPlayerState(filename) {
        try {
            console.log(`Cleaning up video player state for: ${filename}`);
            
            // Check if video player modal is showing this video
            const videoPlayerModal = document.getElementById('videoPlayerModal');
            if (videoPlayerModal && videoPlayerModal.classList.contains('show')) {
                // Get current video info from modal
                const currentFilename = document.getElementById('videoFilename')?.textContent;
                
                if (currentFilename === filename) {
                    console.log(`Video player modal is showing the video to be deleted: ${filename}`);
                    
                    // STEP 1: Stop video playback completely
                    if (window.videoPlayer) {
                        try {
                            // Stop update intervals
                            if (typeof window.videoPlayer.stopUpdateInterval === 'function') {
                                window.videoPlayer.stopUpdateInterval();
                            }
                            
                            // Clean up video element
                            if (window.videoPlayer.video) {
                                const video = window.videoPlayer.video;
                                
                                // Pause and reset video
                                video.pause();
                                video.currentTime = 0;
                                video.volume = 0;
                                video.muted = true;
                                
                                // Remove all event listeners
                                video.onloadstart = null;
                                video.onloadedmetadata = null;
                                video.oncanplay = null;
                                video.onplay = null;
                                video.onpause = null;
                                video.onended = null;
                                video.onerror = null;
                                video.onabort = null;
                                video.onstalled = null;
                                
                                // Clear video source
                                video.src = '';
                                video.load();
                                
                                console.log(`Video element cleaned up for: ${filename}`);
                            }
                        } catch (e) {
                            console.warn('Error cleaning up video player:', e);
                        }
                    }
                    
                    // STEP 2: Clean up video player modal state
                    if (videoPlayerModal._modalInstance) {
                        try {
                            videoPlayerModal._modalInstance.dispose();
                            delete videoPlayerModal._modalInstance;
                        } catch (e) {
                            console.warn('Error disposing modal instance:', e);
                        }
                    }
                    
                    // STEP 3: Force close modal
                    videoPlayerModal.classList.remove('show', 'fade', 'modal-open');
                    videoPlayerModal.style.display = 'none';
                    videoPlayerModal.style.paddingRight = '';
                    videoPlayerModal.removeAttribute('aria-modal');
                    videoPlayerModal.setAttribute('aria-hidden', 'true');
                    
                    // Remove backdrop and body classes
                    document.body.classList.remove('modal-open');
                    document.body.style.paddingRight = '';
                    const backdrops = document.querySelectorAll('.modal-backdrop');
                    backdrops.forEach(backdrop => backdrop.remove());
                    
                    console.log(`Video player modal force-closed for: ${filename}`);
                }
            }
            
            // STEP 4: Clean up any remaining video elements in gallery
            const galleryVideos = document.querySelectorAll(`.gallery-item[data-filename="${filename}"] video`);
            galleryVideos.forEach(video => {
                try {
                    video.pause();
                    video.currentTime = 0;
                    video.src = '';
                    video.load();
                } catch (e) {
                    console.warn('Error cleaning up gallery video:', e);
                }
            });
            
            // STEP 5: Force garbage collection for large videos
            if (typeof window.gc === 'function') {
                try {
                    window.gc();
                    console.log('Garbage collection triggered');
                } catch (e) {
                    console.warn('Garbage collection not available:', e);
                }
            }
            
            // STEP 6: Additional memory cleanup for large videos
            try {
                // Clear any cached video data
                if ('caches' in window) {
                    const cacheNames = await caches.keys();
                    for (const cacheName of cacheNames) {
                        if (cacheName.includes('video') || cacheName.includes('media')) {
                            await caches.delete(cacheName);
                            console.log(`Cleared video cache: ${cacheName}`);
                        }
                    }
                }
                
                // Clear any stored video data in IndexedDB
                if ('indexedDB' in window) {
                    try {
                        const db = await indexedDB.open('video-cache');
                        if (db.result) {
                            const transaction = db.result.transaction(['videos'], 'readwrite');
                            const store = transaction.objectStore('videos');
                            await store.clear();
                            console.log('Cleared IndexedDB video cache');
                        }
                    } catch (e) {
                        // IndexedDB might not exist, ignore
                    }
                }
                
                // Force memory cleanup
                if (window.performance && window.performance.memory) {
                    const memoryInfo = window.performance.memory;
                    console.log(`Memory before cleanup: ${Math.round(memoryInfo.usedJSHeapSize / 1024 / 1024)}MB`);
                }
                
            } catch (e) {
                console.warn('Error during additional memory cleanup:', e);
            }
            
            console.log(`Video player state cleanup completed for: ${filename}`);
            
        } catch (error) {
            console.error(`Error during video player state cleanup for ${filename}:`, error);
        }
    }

    // Force close video player modal and clean up all state
    forceCloseVideoPlayerModal() {
        try {
            const videoPlayerModal = document.getElementById('videoPlayerModal');
            if (videoPlayerModal) {
                // First, stop any playing video
                if (window.videoPlayer) {
                    try {
                        window.videoPlayer.stopUpdateInterval();
                        if (window.videoPlayer.video) {
                            window.videoPlayer.video.pause();
                            window.videoPlayer.video.currentTime = 0;
                            window.videoPlayer.video.src = '';
                            window.videoPlayer.video.load();
                        }
                    } catch (e) {
                        console.warn('Error stopping video player:', e);
                    }
                }
                
                // Force close modal by removing all classes and styles
                videoPlayerModal.classList.remove('show', 'fade', 'modal-open');
                videoPlayerModal.style.display = 'none';
                videoPlayerModal.style.paddingRight = '';
                videoPlayerModal.removeAttribute('aria-modal');
                videoPlayerModal.removeAttribute('aria-hidden');
                videoPlayerModal.setAttribute('aria-hidden', 'true');
                
                // Remove modal backdrop
                document.body.classList.remove('modal-open');
                document.body.style.paddingRight = '';
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => backdrop.remove());
                
                // Dispose modal instance if exists
                if (videoPlayerModal._modalInstance) {
                    try {
                        videoPlayerModal._modalInstance.dispose();
                    } catch (e) {
                        console.warn('Error disposing modal instance:', e);
                    }
                    delete videoPlayerModal._modalInstance;
                }
                
                console.log('Video player modal force-closed and cleaned up');
            }
        } catch (error) {
            console.error('Error force-closing video player modal:', error);
        }
    }

    // Close modals that might be showing the deleted video
    closeModalsForVideo(filename) {
        try {
            // Close video player modal if it's showing the deleted video
            const videoPlayerModal = document.getElementById('videoPlayerModal');
            if (videoPlayerModal) {
                // Use the force close method for more reliable cleanup
                this.forceCloseVideoPlayerModal();
                console.log('Video player modal force-closed for deleted video:', filename);
            }
            
            // Close gallery modal if it's showing the deleted video
            const galleryModal = document.getElementById('galleryModal');
            if (galleryModal) {
                const modal = bootstrap.Modal.getInstance(galleryModal);
                if (modal) {
                    // Check if modal is already being hidden to prevent errors
                    if (!galleryModal.classList.contains('hiding')) {
                        modal.hide();
                        console.log('Gallery modal closed for deleted video:', filename);
                    }
                }
            }
            
            // Update modal state
            this.modalState.isOpen = false;
            this.modalState.currentVideo = null;
            
            // Additional cleanup to ensure modal state is completely reset
            setTimeout(() => {
                // Double-check that modal is actually closed
                const videoPlayerModal = document.getElementById('videoPlayerModal');
                if (videoPlayerModal && (videoPlayerModal.classList.contains('show') || videoPlayerModal.style.display === 'block')) {
                    console.log('Modal still open after cleanup, forcing closure...');
                    this.forceCloseVideoPlayerModal();
                }
            }, 100);
            

            
        } catch (error) {
            console.error('Error closing modals for deleted video:', error);
        }
    }

    // Re-enable delete buttons after video deletion
    reEnableDeleteButtons(filename) {
        try {
            // Re-enable gallery delete button
            const galleryItems = document.querySelectorAll('.gallery-item');
            galleryItems.forEach(item => {
                if (item.dataset.filename === filename) {
                    const deleteBtn = item.querySelector('.delete-video-btn');
                    if (deleteBtn) {
                        deleteBtn.disabled = false;
                        deleteBtn.style.opacity = '1';
                    }
                }
            });
            
            // Re-enable video player modal delete button
            const videoPlayerModal = document.getElementById('videoPlayerModal');
            if (videoPlayerModal) {
                const deleteBtn = videoPlayerModal.querySelector('#deleteVideoBtn');
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.style.opacity = '1';
                }
            }
            
        } catch (error) {
            console.error('Error re-enabling delete buttons:', error);
        }
    }

    // Disable photo delete buttons during deletion
    disablePhotoDeleteButtons(filename) {
        try {
            // Disable gallery photo delete buttons
            const galleryItems = document.querySelectorAll('.gallery-item');
            galleryItems.forEach(item => {
                if (item.dataset.filename === filename) {
                    const deleteBtn = item.querySelector('.delete-photo-btn');
                    if (deleteBtn) {
                        deleteBtn.disabled = true;
                        deleteBtn.style.opacity = '0.6';
                    }
                }
            });
            
            // Disable image modal delete button
            const imageModal = document.getElementById('imageModal');
            if (imageModal) {
                const deleteBtn = imageModal.querySelector('.btn-danger');
                if (deleteBtn) {
                    deleteBtn.disabled = true;
                    deleteBtn.style.opacity = '0.6';
                }
            }
            
        } catch (error) {
            console.error('Error disabling photo delete buttons:', error);
        }
    }

    // Re-enable photo delete buttons after photo deletion
    reEnablePhotoDeleteButtons(filename) {
        try {
            // Re-enable gallery photo delete buttons
            const galleryItems = document.querySelectorAll('.gallery-item');
            galleryItems.forEach(item => {
                if (item.dataset.filename === filename) {
                    const deleteBtn = item.querySelector('.delete-photo-btn');
                    if (deleteBtn) {
                        deleteBtn.disabled = false;
                        deleteBtn.style.opacity = '1';
                    }
                }
            });
            
            // Re-enable image modal delete button
            const imageModal = document.getElementById('imageModal');
            if (imageModal) {
                const deleteBtn = imageModal.querySelector('.btn-danger');
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.style.opacity = '1';
                }
            }
            
        } catch (error) {
            console.error('Error re-enabling photo delete buttons:', error);
        }
    }

    // Remove photo from gallery with animation
    removePhotoFromGallery(filename) {
        const galleryContainer = document.getElementById('galleryContainer');
        if (!galleryContainer) return;
        
        const photoItems = galleryContainer.querySelectorAll('.gallery-item');
        photoItems.forEach(item => {
            if (item.dataset.filename === filename) {
                // Remove all event listeners to prevent conflicts
                const newItem = item.cloneNode(true);
                if (item.parentNode) {
                    item.parentNode.replaceChild(newItem, item);
                }
                
                // Animate removal
                newItem.style.opacity = '0';
                newItem.style.transform = 'scale(0.8)';
                newItem.style.transition = 'all 0.3s ease';
                
                setTimeout(() => {
                    if (newItem.parentNode) {
                        newItem.parentNode.removeChild(newItem);
                    }
                }, 300);
            }
        });
    }

    // Close all modals immediately
    closeAllModals() {
        try {
            // Close image modal
            const imageModal = document.getElementById('imageModal');
            if (imageModal) {
                const modal = bootstrap.Modal.getInstance(imageModal);
                if (modal) {
                    modal.hide();
                    console.log('Image modal closed immediately');
                }
            }
            
            // Close gallery modal
            const galleryModal = document.getElementById('galleryModal');
            if (galleryModal) {
                const modal = bootstrap.Modal.getInstance(galleryModal);
                if (modal) {
                    modal.hide();
                    console.log('Gallery modal closed immediately');
                }
            }
            
            // Close video player modal
            const videoPlayerModal = document.getElementById('videoPlayerModal');
            if (videoPlayerModal) {
                const modal = bootstrap.Modal.getInstance(videoPlayerModal);
                if (modal) {
                    modal.hide();
                    console.log('Video player modal closed immediately');
                }
            }
            
            // Remove backdrop manually to prevent black overlay
            this.removeModalBackdrop();
            
            // Update modal state
            this.modalState.isOpen = false;
            this.modalState.currentImage = null;
            this.modalState.currentVideo = null;
            
        } catch (error) {
            console.error('Error closing all modals:', error);
        }
    }

    // Remove modal backdrop to prevent black overlay
    removeModalBackdrop() {
        try {
            // Remove Bootstrap backdrop
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
                console.log('Modal backdrop removed');
            }
            
            // Remove any remaining backdrop elements
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => backdrop.remove());
            
            // Remove modal-open class from body
            document.body.classList.remove('modal-open');
            
            // Remove padding-right that Bootstrap adds
            document.body.style.paddingRight = '';
            
            // Remove overflow hidden
            document.body.style.overflow = '';
            
        } catch (error) {
            console.error('Error removing modal backdrop:', error);
        }
    }

    // Close modals that might be showing the deleted photo
    closeModalsForPhoto(filename) {
        try {
            // Close image modal if it's showing the deleted photo
            const imageModal = document.getElementById('imageModal');
            if (imageModal) {
                const modal = bootstrap.Modal.getInstance(imageModal);
                if (modal) {
                    // Check if modal is already being hidden to prevent errors
                    if (!imageModal.classList.contains('hiding')) {
                        modal.hide();
                        console.log('Image modal closed for deleted photo:', filename);
                    }
                }
            }
            
            // Close gallery modal if it's showing the deleted photo
            const galleryModal = document.getElementById('galleryModal');
            if (galleryModal) {
                const modal = bootstrap.Modal.getInstance(galleryModal);
                if (modal) {
                    // Check if modal is already being hidden to prevent errors
                    if (!galleryModal.classList.contains('hiding')) {
                        modal.hide();
                        console.log('Gallery modal closed for deleted photo:', filename);
                    }
                }
            }
            
            // Remove backdrop to prevent black overlay
            this.removeModalBackdrop();
            
            // Update modal state
            this.modalState.isOpen = false;
            this.modalState.currentImage = null;
            
        } catch (error) {
            console.error('Error closing modals for deleted photo:', error);
        }
    }

    handleCommandResponse(data) {
        const command = data.command;
        if (data.status === 'success') {
            if (command.type === 'servo') {
                this.showNotification(this.getTranslation('servoCommandSent'), 'success');
            } else if (command.type === 'device_mode') {
                this.deviceMode = command.device_mode;
                this.updateStreamResolution();
                this.showNotification(this.getTranslation(command.device_mode === 'mobile' ? 'mobileMode' : 'desktopMode'), 'info');
            } else if (command.type === 'action') {
                this.showNotification(this.getTranslation(command.action === 'start_recording' ? 'recordingStarted' : 'recordingStopped'), 'success');
            }
        } else if (data.status === 'warning') {
            this.showNotification(data.message || 'دستور با هشدار اجرا شد', 'warning');
        } else {
            this.showNotification(data.message || 'دستور با خطا مواجه شد', 'error');
        }
    }

    async toggleStream() {
        try {
            const btn = document.getElementById('toggleStreamBtn');
            const placeholder = document.getElementById('streamPlaceholder');
            const video = document.getElementById('streamVideo');

            if (!btn || !video || !placeholder) {
                console.warn('[DEBUG] Required elements not found for stream toggle');
                return;
            }

            if (!this.isStreaming) {
                // Start streaming
                console.log('[DEBUG] Starting stream...');
                
                // Initialize frame statistics
                this.frameUpdateCount = 0;
                this.frameStartTime = Date.now();
                this.lastFrameTime = Date.now();
                
                // Check if WebSocket is already connected
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    console.log('[DEBUG] WebSocket already connected, starting stream');
                    this.isStreaming = true;
                    this.updateStreamButton();
                    placeholder.style.display = 'none';
                    video.classList.add('active');
                    this.updateStreamResolution();
                    this.showNotification(this.getTranslation('streamStarted'), 'success');
                } else {
                    // Setup WebSocket connection
                    console.log('[DEBUG] Setting up WebSocket connection for stream');
                    await this.setupWebSocket();
                    
                    // Wait for connection to be established
                    let attempts = 0;
                    const maxAttempts = 30; // Increased attempts
                    while (attempts < maxAttempts) {
                        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                            console.log('[DEBUG] WebSocket connected, starting stream');
                            this.isStreaming = true;
                            this.updateStreamButton();
                            placeholder.style.display = 'none';
                            video.classList.add('active');
                            this.updateStreamResolution();
                            this.showNotification(this.getTranslation('streamStarted'), 'success');
                            break;
                        }
                        await new Promise(resolve => setTimeout(resolve, 200)); // Reduced wait time
                        attempts++;
                        console.log(`[DEBUG] Connection attempt ${attempts}/${maxAttempts}, WebSocket state:`, this.websocket?.readyState);
                    }
                    
                    if (attempts >= maxAttempts) {
                        console.error('[DEBUG] Failed to establish WebSocket connection after', maxAttempts, 'attempts');
                        this.showNotification(this.getTranslation('connectionError'), 'error');
                        return;
                    }
                }
            } else {
                // Stop streaming
                console.log('[DEBUG] Stopping stream...');
                
                // Stop ping-pong mechanism
                this.stopPingPong();
                
                // Close WebSocket connection
                if (this.websocket) {
                    this.websocket.close(1000, 'User stopped streaming');
                    this.websocket = null;
                }
                
                this.isStreaming = false;
                this.updateStreamButton();
                video.classList.remove('active');
                video.src = '';
                placeholder.style.display = 'flex';
                this.showNotification(this.getTranslation('streamStopped'), 'info');
                
                console.log('[DEBUG] Stream stopped successfully');
            }
        } catch (error) {
            console.error('[DEBUG] Error in toggleStream:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
            
            // Test connection for debugging
            this.testWebSocketConnection();
        }
    }

    updateStreamResolution() {
        const video = document.getElementById('streamVideo');
        if (video && this.isStreaming) {
            const { width, height } = this.resolution[this.deviceMode];
            video.style.width = `${width}px`;
            video.style.height = `${height}px`;
        }
    }

    // Test WebSocket connection
    testWebSocketConnection() {
        console.log('[DEBUG] Testing WebSocket connection...');
        if (this.websocket) {
            console.log('[DEBUG] WebSocket state:', this.websocket.readyState);
            console.log('[DEBUG] WebSocket URL:', this.websocket.url);
        } else {
            console.log('[DEBUG] No WebSocket connection');
        }
    }

    updateDeviceModeButton() {
        const btn = document.getElementById('deviceModeToggle');
        if (!btn) return;
        btn.innerHTML = `<i class="fas fa-${this.deviceMode === 'mobile' ? 'mobile-alt' : 'desktop'} me-2"></i> ${this.getTranslation(this.deviceMode === 'mobile' ? 'mobileMode' : 'desktopMode')}`;
        btn.classList.toggle('btn-outline-secondary', this.deviceMode === 'desktop');
        btn.classList.toggle('btn-outline-primary', this.deviceMode === 'mobile');
    }

    async toggleDeviceMode() {
        try {
            const btn = document.getElementById('deviceModeToggle');
            if (!btn) return;
            const prevMode = localStorage.getItem('device_mode') || this.deviceMode || 'desktop';
            this.deviceMode = this.deviceMode === 'desktop' ? 'mobile' : 'desktop';
            
            // Update localStorage immediately
            localStorage.setItem('device_mode', this.deviceMode);
            
            // Update button UI immediately
            this.updateDeviceModeButton();
            
            // Show notification
            if (prevMode !== this.deviceMode) {
                this.showNotification(this.getTranslation(this.deviceMode === 'mobile' ? 'mobileMode' : 'desktopMode'), 'info');
            }
            
            // Send to server via HTTP
            try {
                const response = await fetch('/set_device_mode', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                    },
                    body: JSON.stringify({device_mode: this.deviceMode}),
                    credentials: 'include'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                // Update stream resolution after successful mode change
                this.updateStreamResolution();
                
            } catch (httpError) {
                console.error('HTTP error in device mode change:', httpError);
                // Revert the change if server update failed
                this.deviceMode = prevMode;
                localStorage.setItem('device_mode', prevMode);
                this.updateDeviceModeButton();
                this.showNotification('خطا در بروزرسانی سرور - تغییرات لغو شد', 'error');
                return;
            }
            
            // Save user settings to server
            this.saveUserSettingsToServer();
            
        } catch (error) {
            console.error('خطا در تغییر حالت دستگاه:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    async capturePhoto() {
        try {
            // Check ESP32CAM status first
            const esp32camStatus = await this.checkESP32CAMStatus();
            if (!esp32camStatus.connected) {
                this.showNotification('ESP32CAM متصل نیست - لطفاً اتصال را بررسی کنید', 'warning');
                console.warn('[DEBUG] capturePhoto - ESP32CAM not connected:', esp32camStatus);
                return;
            }
            
            const quality = document.getElementById('photoQuality')?.value || 80;
            const flashEnabled = document.getElementById('flashToggle')?.checked || false;
            const flashIntensity = document.getElementById('flashIntensity')?.value || 50;
            
            console.log(`[DEBUG] capturePhoto - quality: ${quality} (${typeof quality}), flash: ${flashEnabled} (${typeof flashEnabled}), intensity: ${flashIntensity} (${typeof flashIntensity})`);
            
            // Validate data types before sending
            const photoData = {
                quality: Math.max(1, Math.min(100, parseInt(quality) || 80)),
                flash: Boolean(flashEnabled),
                intensity: Math.max(0, Math.min(100, parseInt(flashIntensity) || 50))
            };
            
            console.log(`[DEBUG] capturePhoto - validated data:`, photoData);
            console.log(`[DEBUG] capturePhoto - data types:`, {
                quality: `${photoData.quality} (${typeof photoData.quality})`,
                flash: `${photoData.flash} (${typeof photoData.flash})`,
                intensity: `${photoData.intensity} (${typeof photoData.intensity})`
            });
            
            if (photoData.quality < 1 || photoData.quality > 100) {
                throw new Error('Quality must be between 1 and 100');
            }
            if (photoData.intensity < 0 || photoData.intensity > 100) {
                throw new Error('Flash intensity must be between 0 and 100');
            }
            
            const response = await this.handleApiCall('/manual_photo', 'POST', photoData);
            
            if (response.status === 'success') {
                console.log(`[DEBUG] capturePhoto - success response:`, response);
                this.showNotification('عکس با موفقیت گرفته شد', 'success');
            } else {
                console.error(`[DEBUG] capturePhoto - error response:`, response);
                this.showNotification('خطا در گرفتن عکس', 'error');
            }
        } catch (error) {
            console.error('[DEBUG] capturePhoto - exception:', error);
            console.error('[DEBUG] capturePhoto - error details:', {
                message: error.message,
                stack: error.stack,
                name: error.name
            });
            this.showNotification(`خطا: ${error.message}`, 'error');
        }
    }

    // Add missing methods
    async checkESP32CAMStatus() {
        try {
            const response = await fetch('/get_esp32cam_status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                },
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                return data.status === 'success' ? data.data : { connected: false };
            }
            return { connected: false };
        } catch (error) {
            console.error('Error checking ESP32CAM status:', error);
            return { connected: false };
        }
    }

    async handleApiCall(endpoint, method, data = null) {
        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                },
                credentials: 'include'
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(endpoint, options);
            const result = await response.json();
            
            return result;
        } catch (error) {
            console.error(`API call error for ${endpoint}:`, error);
            return { status: 'error', message: error.message };
        }
    }

    updateFlashUI(enabled, intensity) {
        const flashToggle = document.getElementById('flashToggle');
        const flashIntensity = document.getElementById('flashIntensity');
        const flashControls = document.getElementById('flashControls');
        
        if (flashToggle) flashToggle.checked = enabled;
        if (flashIntensity) flashIntensity.value = intensity;
        if (flashControls) flashControls.classList.toggle('active', enabled);
        
        this.updateFlashIntensityValue(intensity);
    }

    saveFlashSettings(enabled, intensity) {
        const flashSettings = {
            intensity: intensity,
            enabled: enabled
        };
        localStorage.setItem('flashSettings', JSON.stringify(flashSettings));
        this.saveUserSettingsToServer();
    }

    updateQualityValue(value) {
        const qualityValue = document.getElementById('qualityValue');
        if (qualityValue) qualityValue.textContent = `${value}%`;
    }

    updateFlashIntensityValue(value) {
        const flashIntensityValue = document.getElementById('flashIntensityValue');
        if (flashIntensityValue) {
            flashIntensityValue.textContent = `${value}%`;
            localStorage.setItem('flashSettings', JSON.stringify({
                intensity: value,
                enabled: document.getElementById('flashToggle')?.checked || false
            }));
            this.saveUserSettingsToServer();
        }
    }

    async toggleFlash() {
        try {
            // Check ESP32CAM status first
            const esp32camStatus = await this.checkESP32CAMStatus();
            if (!esp32camStatus.connected) {
                this.showNotification('ESP32CAM متصل نیست - لطفاً اتصال را بررسی کنید', 'warning');
                console.warn('[DEBUG] toggleFlash - ESP32CAM not connected:', esp32camStatus);
                return;
            }
            
            const flashEnabled = document.getElementById('flashToggle')?.checked || false;
            const intensityValue = document.getElementById('flashIntensity')?.value || 50;
            const intensity = Math.max(0, Math.min(100, parseInt(intensityValue) || 50));
            
            console.log(`[DEBUG] toggleFlash - flashEnabled: ${flashEnabled}, intensity: ${intensity}, type: ${typeof intensity}`);
            
            const action = flashEnabled ? 'flash_on' : 'flash_off';
            const photoData = {
                action: action,
                intensity: intensity
            };
            
            console.log(`[DEBUG] toggleFlash - sending data:`, photoData);
            
            const response = await this.handleApiCall('/set_action', 'POST', photoData);
            
            if (response.status === 'success') {
                console.log(`[DEBUG] toggleFlash - success response:`, response);
                // Update UI state
                this.updateFlashUI(flashEnabled, intensity);
                // Save to localStorage
                this.saveFlashSettings(flashEnabled, intensity);
                this.showNotification(`فلش ${flashEnabled ? 'فعال' : 'غیرفعال'} شد`, 'success');
            } else {
                console.error(`[DEBUG] toggleFlash - error response:`, response);
                this.showNotification('خطا در تنظیم فلش', 'error');
            }
        } catch (error) {
            console.error('[DEBUG] toggleFlash - exception:', error);
            console.error('[DEBUG] toggleFlash - error details:', {
                message: error.message,
                stack: error.stack,
                name: error.name
            });
            this.showNotification(`خطا در تنظیم فلش: ${error.message}`, 'error');
        }
    }

    async sendServoCommand() {
        const btn = document.getElementById('sendServoBtn');
        if (btn && btn.disabled) {
            this.showNotification('دستور سروو در حال ارسال است، لطفاً صبر کنید...', 'warning');
            return; // جلوگیری از ارسال همزمان
        }
        
        if (btn) btn.disabled = true; // غیرفعال کردن دکمه تا دریافت پاسخ
        
        try {
            const servoX = document.getElementById('servoX')?.value || 90;
            const servoY = document.getElementById('servoY')?.value || 90;

            if (servoX < 0 || servoX > 180 || servoY < 0 || servoY > 180) {
                this.showNotification(this.getTranslation('angleError'), 'error');
                return;
            }

            // ارسال از طریق HTTP endpoint (مسیر صحیح)
            const res = await fetch('/set_servo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                },
                body: JSON.stringify({servo1: parseInt(servoX), servo2: parseInt(servoY)}),
                credentials: 'include'
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showNotification(this.getTranslation('servoCommandSent'), 'success');
            } else {
                this.showNotification(data.message || this.getTranslation('settingsError'), 'error');
            }
        } catch (error) {
            console.error('خطا در ارسال دستور سروو:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        } finally {
            if (btn) btn.disabled = false; // فعال کردن مجدد دکمه
        }
    }

    async resetServo() {
        try {
            const servoX = document.getElementById('servoX');
            const servoXNumber = document.getElementById('servoXNumber');
            const servoY = document.getElementById('servoY');
            const servoYNumber = document.getElementById('servoYNumber');

            if (servoX) servoX.value = 90;
            if (servoXNumber) servoXNumber.value = 90;
            if (document.getElementById('servoXValue')) document.getElementById('servoXValue').textContent = '90°';
            if (servoY) servoY.value = 90;
            if (servoYNumber) servoYNumber.value = 90;
            if (document.getElementById('servoYValue')) document.getElementById('servoYValue').textContent = '90°';

            // ارسال از طریق HTTP endpoint (مسیر صحیح)
            const res = await fetch('/set_servo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                },
                body: JSON.stringify({servo1: 90, servo2: 90}),
                credentials: 'include'
            });
            const data = await res.json();
            if (data.status === 'success') {
                this.showNotification(this.getTranslation('servosReset'), 'success');
            } else {
                this.showNotification(data.message || this.getTranslation('settingsError'), 'error');
            }
        } catch (error) {
            console.error('خطا در بازنشانی سرووها:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    async loadGallery() {
        if (this.isLoading) return;
        this.isLoading = true;

        try {
            const response = await fetch(`/get_gallery?page=${this.currentPage}`, { credentials: 'include' });
            if (!response.ok) throw new Error('Failed to fetch gallery');
            // Be defensive: server always returns JSON, but avoid breaking UI if HTML error is returned
            let data;
            try {
                data = await response.json();
            } catch (e) {
                data = { status: response.ok ? 'success' : 'error', message: 'Unexpected response format' };
            }

            const galleryContainer = document.getElementById('galleryContainer');
            if (!galleryContainer) return;

            if (this.currentPage === 0) galleryContainer.innerHTML = '';

            data.photos.forEach(photo => {
                const item = document.createElement('div');
                item.className = 'gallery-item';
                item.dataset.url = photo.url;
                item.dataset.timestamp = new Date(photo.timestamp).toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US');
                item.dataset.filename = photo.filename; // اضافه کردن filename به dataset برای تصویر
                // Compute weekday
                const dateObj = new Date(photo.timestamp);
                const weekdays = this.language === 'fa' ? [
                    this.getTranslation('weekday_sun','یکشنبه'),
                    this.getTranslation('weekday_mon','دوشنبه'),
                    this.getTranslation('weekday_tue','سه‌شنبه'),
                    this.getTranslation('weekday_wed','چهارشنبه'),
                    this.getTranslation('weekday_thu','پنجشنبه'),
                    this.getTranslation('weekday_fri','جمعه'),
                    this.getTranslation('weekday_sat','شنبه')
                ] : [
                    this.getTranslation('weekday_sun','Sunday'),
                    this.getTranslation('weekday_mon','Monday'),
                    this.getTranslation('weekday_tue','Tuesday'),
                    this.getTranslation('weekday_wed','Wednesday'),
                    this.getTranslation('weekday_thu','Thursday'),
                    this.getTranslation('weekday_fri','Friday'),
                    this.getTranslation('weekday_sat','Saturday')
                ];
                const weekday = weekdays[dateObj.getDay()];
                const dateStr = dateObj.toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US');
                // Detect mobile mode
                const isMobile = this.deviceMode === 'mobile' || window.innerWidth <= 600;
                item.innerHTML = `
                    <img src="${photo.url}" alt="${this.language === 'fa' ? 'تصویر امنیتی' : 'Security Image'}" loading="lazy">
                    ${isMobile ? `
                    <div class="gallery-info-overlay" style="position:absolute;bottom:0;left:0;width:100%;background:rgba(0,0,0,0.55);color:#fff;padding:4px 6px;font-size:0.95em;display:flex;flex-direction:row;align-items:center;gap:10px;justify-content:center;z-index:2;">
                        <span style="display:flex;align-items:center;gap:3px;white-space:nowrap;">
                            <i class='fas fa-calendar-alt' style='color:#ffd700;'></i>
                            <span>${dateStr}</span>
                        </span>
                        <span style="display:flex;align-items:center;gap:3px;white-space:nowrap;">
                            <i class='fas fa-calendar-day' style='color:#ff9800;'></i>
                            <span>${weekday}</span>
                        </span>
                    </div>
                    ` : `
                    <div class="gallery-info" style="display:flex;flex-direction:row;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-start;overflow:hidden;">
                        <span style="display:flex;align-items:center;gap:4px;white-space:nowrap;">
                            <i class="fas fa-calendar-alt" style="color:#6c63ff;"></i>
                            <span style="font-weight:bold;">${this.language === 'fa' ? 'تاریخ:' : 'Date:'}</span>
                            <span>${dateStr}</span>
                        </span>
                        <span style="display:flex;align-items:center;gap:4px;white-space:nowrap;">
                            <i class="fas fa-calendar-day" style="color:#ff9800;"></i>
                            <span style="font-weight:bold;">${this.language === 'fa' ? 'روز:' : 'Weekday:'}</span>
                            <span>${weekday}</span>
                        </span>
                    </div>
                    `}
                    <div class="gallery-actions">
                        <button class="btn btn-sm btn-outline-success download-photo-btn" title="${this.language === 'fa' ? 'دانلود' : 'Download'}">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger delete-photo-btn" title="${this.language === 'fa' ? 'حذف' : 'Delete'}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                `;
                if (isMobile) item.style.position = 'relative';
                
                // Add click event for showing modal
                item.addEventListener('click', (e) => {
                    // Don't show modal if clicking on buttons
                    if (e.target.closest('.gallery-actions')) {
                        return;
                    }
                    this.showGalleryModal(photo.url, dateStr, false, photo.filename, weekday);
                });
                
                // Add event listeners for buttons
                const downloadBtn = item.querySelector('.download-photo-btn');
                if (downloadBtn) {
                    downloadBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        this.downloadImage(photo.url, photo.filename);
                    });
                }
                
                const deleteBtn = item.querySelector('.delete-photo-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Check if photo is already being deleted
                        if (this.deletingPhotos && this.deletingPhotos.has(photo.filename)) {
                            console.log(`Photo ${photo.filename} is already being deleted, skipping action`);
                            return;
                        }
                        
                        if (confirm(this.language === 'fa' ? 'آیا از حذف این تصویر اطمینان دارید؟' : 'Are you sure you want to delete this image?')) {
                            // Close any open modals immediately
                            this.closeAllModals();
                            // Start deletion process
                            this.deletePhoto(photo.filename, item);
                        }
                    });
                }
                
                galleryContainer.appendChild(item);
            });

            this.currentPage++;
            if (!data.has_more) {
                const loadMoreBtn = document.getElementById('loadMoreBtn');
                if (loadMoreBtn) loadMoreBtn.style.display = 'none';
            }
        } catch (error) {
            this.showNotification(this.getTranslation('galleryError'), 'error', {
                title: this.getTranslation('galleryError'),
                message: error.message,
                code: error.code || '-',
                source: 'fetch(/get_gallery)'
            });
        } finally {
            this.isLoading = false;
        }
    }

    async deletePhoto(filename, domItem = null) {
        try {
            // Prevent duplicate requests more robustly
            if (this.deletingPhotos && this.deletingPhotos.has(filename)) {
                console.log(`Photo ${filename} is already being deleted, skipping duplicate request`);
                return;
            }
            
            // Initialize deletingPhotos set if not exists
            if (!this.deletingPhotos) {
                this.deletingPhotos = new Set();
            }
            
            // Add to deleting set immediately
            this.deletingPhotos.add(filename);
            console.log(`Deleting photo: ${filename}`);
            
            // Disable all delete buttons for this photo immediately
            this.disablePhotoDeleteButtons(filename);
            
            // Close all modals immediately before deletion
            this.closeAllModals();
            
                    // Close modal if open and this photo is currently displayed
        if (this.modalState.isOpen && this.modalState.currentImage === filename) {
            const modalEl = document.getElementById('imageModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) {
                    modal.hide();
                    // Wait for modal to close before proceeding
                    await new Promise(resolve => setTimeout(resolve, 300));
                }
            }
        }
        
        // Close image modal if it's showing this photo
        this.closeModalsForPhoto(filename);
        
        // Ensure backdrop is removed
        this.removeModalBackdrop();
            
            // Clean up photo elements from gallery immediately
            this.removePhotoFromGallery(filename);
            
            // Delete from server
            const response = await fetch(`/delete_photo/${filename}`, {
                method: 'POST',
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                    'Content-Type': 'application/json',
                    ...(this.csrfToken ? { 'X-CSRF-Token': this.csrfToken } : {})
                },
                credentials: 'include'
            });
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Authentication failed - don't redirect, just show error
                    throw new Error('Authentication failed. Please refresh the page and try again.');
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                // If not JSON, check if it's a 404 (file already deleted)
                if (response.status === 404) {
                    console.log(`Photo ${filename} already deleted or not found`);
                    this.showNotification('تصویر با موفقیت حذف شد', 'success');
                    this.currentPage = 0;
                    await this.loadGallery();
                    return;
                }
                throw new Error(`Unexpected response format: ${contentType}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showNotification(data.message || 'تصویر با موفقیت حذف شد', 'success');
                
                // Refresh gallery to update pagination
                this.currentPage = 0;
                await this.loadGallery();
            } else {
                throw new Error(data.message || 'خطا در حذف تصویر');
            }
            
        } catch (error) {
            console.error('Error deleting photo:', error);
            this.showNotification(
                this.language === 'fa' ? 'خطا در حذف تصویر' : 'Error deleting photo',
                'error'
            );
        } finally {
            if (this.deletingPhotos) {
                this.deletingPhotos.delete(filename);
            }
            // Re-enable delete buttons
            this.reEnablePhotoDeleteButtons(filename);
        }
    }

    // Enhanced Video Loading with Memory Management
    async loadVideos() {
        if (this.isLoading) return;
        this.isLoading = true;

        try {
            const response = await fetch(`/get_videos?page=${this.currentVideoPage}`, { 
                credentials: 'include',
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            const data = await response.json();

            const videosContainer = document.getElementById('videosContainer');
            if (!videosContainer) {
                console.warn('Videos container not found');
                return;
            }

            // Clear container if first page
            if (this.currentVideoPage === 0) {
                this.cleanupVideoGallery();
                videosContainer.innerHTML = '';
                // Only clear deleted videos set if no deletions are in progress
                if (this.deletingVideos.size === 0 && !this.isSystemBusy) {
                    console.log('Clearing deleted videos set - no deletions in progress');
                    this.deletedVideos.clear();
                } else {
                    console.log('Keeping deleted videos set - deletions in progress');
                }
            }

            // Check for duplicate videos
            const existingFilenames = new Set();
            if (this.currentVideoPage > 0) {
                videosContainer.querySelectorAll('.gallery-item').forEach(item => {
                    const filename = item.dataset.filename;
                    if (filename) existingFilenames.add(filename);
                });
            }

            if (!data.videos || !Array.isArray(data.videos)) {
                console.warn('Invalid videos data received');
                return;
            }

            data.videos.forEach(video => {
                // Skip if video already exists
                if (existingFilenames.has(video.filename)) {
                    return;
                }

                const videoItem = this.createVideoItem(video);
                if (videoItem) {
                    videosContainer.appendChild(videoItem);
                }
            });

            this.currentVideoPage++;
            
            // Update load more button
            const loadMoreVideosBtn = document.getElementById('loadMoreVideosBtn');
            if (loadMoreVideosBtn) {
                loadMoreVideosBtn.style.display = data.has_more ? 'block' : 'none';
            }

        } catch (error) {
            console.error('Error loading videos:', error);
            this.showNotification(this.getTranslation('galleryError'), 'error', {
                title: this.getTranslation('galleryError'),
                message: error.message,
                code: error.code || '-',
                source: 'fetch(/get_videos)'
            });
        } finally {
            this.isLoading = false;
        }
    }

    // Create video item with proper memory management
    createVideoItem(video) {
        try {
            const item = document.createElement('div');
            item.className = 'gallery-item video-item';
            item.dataset.url = video.url;
            item.dataset.timestamp = new Date(video.timestamp).toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US');
            item.dataset.filename = video.filename;
            item.dataset.isVideo = 'true';
            
            // Calculate weekday
            const dateObj = new Date(video.timestamp);
            const weekdays = this.language === 'fa' ? [
                this.getTranslation('weekday_sun','یکشنبه'),
                this.getTranslation('weekday_mon','دوشنبه'),
                this.getTranslation('weekday_tue','سه‌شنبه'),
                this.getTranslation('weekday_wed','چهارشنبه'),
                this.getTranslation('weekday_thu','پنجشنبه'),
                this.getTranslation('weekday_fri','جمعه'),
                this.getTranslation('weekday_sat','شنبه')
            ] : [
                this.getTranslation('weekday_sun','Sunday'),
                this.getTranslation('weekday_mon','Monday'),
                this.getTranslation('weekday_tue','Tuesday'),
                this.getTranslation('weekday_wed','Wednesday'),
                this.getTranslation('weekday_thu','Thursday'),
                this.getTranslation('weekday_fri','Friday'),
                this.getTranslation('weekday_sat','Saturday')
            ];
            const weekday = weekdays[dateObj.getDay()];
            const dateStr = dateObj.toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US');
            
            // Detect mobile mode
            const isMobile = this.deviceMode === 'mobile' || window.innerWidth <= 600;
            
            // Create video URL
            const videoUrl = video.url.startsWith('/') ? video.url : `/security_videos/${video.filename}`;
            
            // Create video thumbnail with proper event handling
            item.innerHTML = `
                <div class="video-thumbnail">
                    <video data-src="${videoUrl}" muted preload="metadata" playsinline controlslist="nodownload" disablePictureInPicture disableRemotePlayback poster="/video_poster/${video.filename}">
                        <source src="${videoUrl}" type="video/mp4">
                    </video>
                    <div class="video-overlay">
                        <i class="fas fa-play-circle"></i>
                    </div>
                    <!-- Loading indicator for poster generation -->
                    <div class="video-loading" style="display: none;">
                        <i class="fas fa-spinner fa-spin"></i>
                    </div>
                </div>
                ${isMobile ? `
                <div class="gallery-info-overlay" style="position:absolute;bottom:0;left:0;width:100%;background:rgba(0,0,0,0.55);color:#fff;padding:4px 6px;font-size:0.95em;display:flex;flex-direction:row;align-items:center;gap:10px;justify-content:center;z-index:2;">
                    <span style="display:flex;align-items:center;gap:3px;white-space:nowrap;">
                        <i class='fas fa-calendar-alt' style='color:#ffd700;'></i>
                        <span>${dateStr}</span>
                    </span>
                    <span style="display:flex;align-items:center;gap:3px;white-space:nowrap;">
                        <i class='fas fa-calendar-day' style='color:#ff9800;'></i>
                        <span>${weekday}</span>
                    </span>
                </div>
                ` : `
                <div class="gallery-info" style="display:flex;flex-direction:row;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-start;overflow:hidden;">
                    <span style="display:flex;align-items:center;gap:4px;white-space:nowrap;">
                        <i class="fas fa-calendar-alt" style="color:#6c63ff;"></i>
                        <span style="font-weight:bold;">${this.language === 'fa' ? 'تاریخ:' : 'Date:'}</span>
                        <span>${dateStr}</span>
                    </span>
                    <span style="display:flex;align-items:center;gap:4px;white-space:nowrap;">
                        <i class="fas fa-calendar-day" style="color:#ff9800;"></i>
                        <span style="font-weight:bold;">${this.language === 'fa' ? 'روز:' : 'Weekday:'}</span>
                        <span>${weekday}</span>
                    </span>
                </div>
                `}
                <!-- Enhanced metadata display -->
                <div class="video-metadata" style="display: none;">
                    <div class="metadata-row">
                        <span class="metadata-label">${this.language === 'fa' ? 'رزولوشن:' : 'Resolution:'}</span>
                        <span class="metadata-value resolution-value">--</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">${this.language === 'fa' ? 'مدت:' : 'Duration:'}</span>
                        <span class="metadata-value duration-value">--</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">FPS:</span>
                        <span class="metadata-value fps-value">--</span>
                    </div>
                </div>
            `;
            
            if (isMobile) item.style.position = 'relative';
            
            // Setup video element with proper memory management
            const videoElement = item.querySelector('video');
            if (videoElement) {
                this.setupVideoElement(videoElement, video.filename);
            }
            
            // Add click event for modal with proper cleanup
            const clickHandler = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.showGalleryModal(videoUrl, dateStr, true, video.filename, weekday);
            };
            
            item.addEventListener('click', clickHandler);
            
            // Store cleanup callback
            this.cleanupCallbacks.push(() => {
                item.removeEventListener('click', clickHandler);
                if (videoElement) {
                    this.cleanupVideoElement(videoElement);
                }
            });
            
            return item;
            
        } catch (error) {
            console.error('Error creating video item:', error);
            return null;
        }
    }
    
    // Setup event handlers for video gallery items
    setupVideoItemEventHandlers(item, videoUrl, dateStr, filename, weekday) {
        try {
            // Play video button
            const playBtn = item.querySelector('.play-video-btn');
            if (playBtn) {
                const playHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.showVideoPlayer(videoUrl, dateStr, filename, weekday);
                };
                playBtn.addEventListener('click', playHandler);
                
                // Store cleanup callback
                this.cleanupCallbacks.push(() => {
                    playBtn.removeEventListener('click', playHandler);
                });
            }
            
            // Download video button
            const downloadBtn = item.querySelector('.download-video-btn');
            if (downloadBtn) {
                const downloadHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.downloadVideo(videoUrl, filename);
                };
                downloadBtn.addEventListener('click', downloadHandler);
                
                // Store cleanup callback
                this.cleanupCallbacks.push(() => {
                    downloadBtn.removeEventListener('click', downloadHandler);
                });
            }
            
            // Delete video button
            const deleteBtn = item.querySelector('.delete-video-btn');
            if (deleteBtn) {
                // Capture filename in closure to prevent corruption
                const videoFilename = filename;
                
                const deleteHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    console.log(`Delete button clicked for video: ${videoFilename}`);
                    
                    // Prevent multiple confirmations if video is already being deleted
                    if (this.deletingVideos.has(videoFilename)) {
                        console.log(`Video ${videoFilename} is already being deleted, skipping action`);
                        return;
                    }
                    
                    // Prevent deletion of already deleted videos
                    if (this.deletedVideos.has(videoFilename)) {
                        console.log(`Video ${videoFilename} has already been deleted, skipping action`);
                        this.showNotification(
                            this.language === 'fa' ? 'این ویدیو قبلاً حذف شده است' : 'This video has already been deleted',
                            'info'
                        );
                        return;
                    }
                    
                    // Disable button temporarily to prevent multiple clicks
                    deleteBtn.disabled = true;
                    deleteBtn.style.opacity = '0.6';
                    
                    // Store the filename in a data attribute for verification
                    deleteBtn.setAttribute('data-deleting-filename', videoFilename);
                    
                    if (confirm(this.language === 'fa' ? 'آیا از حذف این ویدیو اطمینان دارید؟' : 'Are you sure you want to delete this video?')) {
                        // Verify filename hasn't changed
                        const currentFilename = deleteBtn.getAttribute('data-deleting-filename');
                        if (currentFilename === videoFilename) {
                            console.log(`Proceeding with deletion of: ${videoFilename}`);
                            this.deleteVideo(videoFilename);
                        } else {
                            console.error(`Filename mismatch! Expected: ${videoFilename}, Got: ${currentFilename}`);
                            this.showNotification(
                                this.language === 'fa' ? 'خطا: نام فایل تغییر کرده است' : 'Error: Filename has changed',
                                'error'
                            );
                        }
                    } else {
                        // Re-enable button if user cancels
                        deleteBtn.disabled = false;
                        deleteBtn.style.opacity = '1';
                        deleteBtn.removeAttribute('data-deleting-filename');
                    }
                };
                
                // Remove existing listener if any
                deleteBtn.removeEventListener('click', deleteHandler);
                deleteBtn.addEventListener('click', deleteHandler);
                
                // Store cleanup callback
                this.cleanupCallbacks.push(() => {
                    deleteBtn.removeEventListener('click', deleteHandler);
                });
            }
            
            // Thumbnail click for play
            const thumbnail = item.querySelector('.video-thumbnail');
            if (thumbnail) {
                const thumbnailHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.showVideoPlayer(videoUrl, dateStr, filename, weekday);
                };
                thumbnail.addEventListener('click', thumbnailHandler);
                
                // Store cleanup callback
                this.cleanupCallbacks.push(() => {
                    thumbnail.removeEventListener('click', thumbnailHandler);
                });
            }
            
        } catch (error) {
            console.error('Error setting up video item event handlers:', error);
        }
    }

    // Setup video element with optimized loading for faster previews
    setupVideoElement(videoElement, filename) {
        if (!videoElement) return;
        
        // Store video element reference
        this.videoElements.set(videoElement, { filename, timestamp: Date.now() });
        this.activeVideos.add(videoElement);
        
        // Setup optimized event listeners for faster previews
        const events = ['loadstart', 'loadedmetadata', 'canplay', 'error', 'abort', 'stalled'];
        const listeners = {};
        
        events.forEach(event => {
            const listener = (e) => this.handleVideoEvent(e, videoElement, filename);
            videoElement.addEventListener(event, listener, { passive: true });
            listeners[event] = listener;
        });
        
        // Store listeners for cleanup
        this.videoEventListeners.set(videoElement, listeners);
        
        // Optimize video loading for faster previews
        this.optimizeVideoLoading(videoElement, filename);
        
        // Load video metadata for enhanced display
        this.loadVideoMetadata(videoElement, filename);
    }

    // Optimize video loading for faster previews
    optimizeVideoLoading(videoElement, filename) {
        try {
            // Set video properties for faster loading
            videoElement.preload = 'metadata';
            videoElement.muted = true;
            videoElement.playsInline = true;
            
            // Use Intersection Observer for lazy loading
            if ('IntersectionObserver' in window) {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            // Load video when it comes into view
                            this.loadVideoPreview(videoElement, filename);
                            observer.unobserve(videoElement);
                        }
                    });
                }, {
                    rootMargin: '50px', // Start loading 50px before video comes into view
                    threshold: 0.1
                });
                
                observer.observe(videoElement);
                
                // Store observer for cleanup
                this.videoObservers.set(videoElement, observer);
            } else {
                // Fallback for older browsers
                this.loadVideoPreview(videoElement, filename);
            }
            
        } catch (error) {
            console.warn('Error optimizing video loading:', error);
            // Fallback to normal loading
            this.loadVideoPreview(videoElement, filename);
        }
    }

    // Load video preview with optimized settings
    loadVideoPreview(videoElement, filename) {
        try {
            // Set source and load metadata only
            const dataSrc = videoElement.dataset.src;
            if (dataSrc && !videoElement.src) {
                videoElement.src = dataSrc;
                videoElement.load();
            }
        } catch (error) {
            console.warn('Error loading video preview:', error);
        }
    }

    // Handle video events
    handleVideoEvent(event, videoElement, filename) {
        switch (event.type) {
            case 'loadstart':
                console.log(`Video loadstart: ${filename}`);
                break;
            case 'loadedmetadata':
                console.log(`Video loadedmetadata: ${filename}`);
                break;
            case 'canplay':
                console.log(`Video canplay: ${filename}`);
                break;
            case 'error':
                console.error(`Video error: ${filename}`, event);
                this.handleVideoError(videoElement, filename);
                break;
            case 'abort':
                console.warn(`Video abort: ${filename}`);
                break;
            case 'stalled':
                console.warn(`Video stalled: ${filename}`);
                break;
        }
    }

    // Handle video error
    handleVideoError(videoElement, filename) {
        console.error(`Video error for ${filename}:`, videoElement.error);
        
        // Remove from active videos
        this.activeVideos.delete(videoElement);
        
        // Show error notification
        this.showNotification(
            this.language === 'fa' ? 'خطا در بارگذاری ویدیو' : 'Error loading video',
            'error'
        );
    }

    // Cleanup video element with observer cleanup
    cleanupVideoElement(videoElement) {
        if (!videoElement) return;
        
        try {
            // Pause and reset video
            videoElement.pause();
            videoElement.currentTime = 0;
            videoElement.removeAttribute('src');
            videoElement.load();
            
            // Remove event listeners
            const listeners = this.videoEventListeners.get(videoElement);
            if (listeners) {
                Object.entries(listeners).forEach(([event, listener]) => {
                    videoElement.removeEventListener(event, listener);
                });
                this.videoEventListeners.delete(videoElement);
            }
            
            // Cleanup intersection observer
            const observer = this.videoObservers.get(videoElement);
            if (observer) {
                observer.disconnect();
                this.videoObservers.delete(videoElement);
            }
            
            // Remove from tracking
            this.activeVideos.delete(videoElement);
            this.videoElements.delete(videoElement);
            
        } catch (error) {
            console.warn('Error cleaning up video element:', error);
        }
    }

    // Cleanup video gallery
    cleanupVideoGallery() {
        const videosContainer = document.getElementById('videosContainer');
        if (!videosContainer) return;
        
        const videoElements = videosContainer.querySelectorAll('video');
        videoElements.forEach(video => {
            this.cleanupVideoElement(video);
        });
        
        // Clear container
        videosContainer.innerHTML = '';
    }

    // Initialize Video Player System
    initializeVideoPlayer() {
        try {
            // Prevent initialization if video deletion is in progress
            if (this.isDeletingVideo) {
                console.log('Video player initialization blocked - video deletion in progress');
                return;
            }
            
            // Prevent multiple video player initializations
            if (window.videoPlayer && window.videoPlayer.isInitialized) {
                console.log('⚠️ Video player already initialized, skipping duplicate initialization');
                return;
            }
            
            // Initialize the modern video player
            if (typeof ModernVideoPlayer !== 'undefined') {
                window.videoPlayer = new ModernVideoPlayer();
                window.videoPlayer.isInitialized = true; // Mark as initialized
                console.log('✅ Video player system initialized');
            } else {
                console.warn('⚠️ ModernVideoPlayer class not found');
            }
        } catch (error) {
            console.error('❌ Error initializing video player:', error);
        }
    }

    // Modern Gallery Modal System
    showGalleryModal(url, timestamp, isVideo = false, filename = '', weekday = '') {
        try {
            // Prevent opening gallery modal if we're currently deleting a video
            if (this.isDeletingVideo && isVideo) {
                console.log('Gallery modal blocked for video - video deletion in progress');
                return;
            }
            
            // Prevent opening gallery modal for already deleted videos
            if (isVideo && this.deletedVideos.has(filename)) {
                console.log('Gallery modal blocked for video - video already deleted:', filename);
                this.showNotification(
                    this.language === 'fa' ? 'این ویدیو قبلاً حذف شده است' : 'This video has already been deleted',
                    'info'
                );
                return;
            }
            
            // Prevent opening gallery modal for videos currently being deleted
            if (isVideo && this.deletingVideos.has(filename)) {
                console.log('Gallery modal blocked for video - video being deleted:', filename);
                this.showNotification(
                    this.language === 'fa' ? 'این ویدیو در حال حذف شدن است' : 'This video is being deleted',
                    'warning'
                );
                return;
            }
            
            if (isVideo) {
                this.showVideoPlayer(url, timestamp, filename, weekday);
            } else {
                this.showImageModal(url, timestamp, weekday);
            }
        } catch (error) {
            console.error('Error showing gallery modal:', error);
            this.showNotification(this.getTranslation('galleryError'), 'error');
        }
    }
    
    // Show Video Player Modal
    showVideoPlayer(url, timestamp, filename, weekday) {
        try {
            // Prevent opening video player if we're currently deleting a video
            if (this.isDeletingVideo) {
                console.log('Video player modal blocked - video deletion in progress');
                return;
            }
            
            // Prevent opening video player for already deleted videos
            if (this.deletedVideos.has(filename)) {
                console.log('Video player modal blocked - video already deleted:', filename);
                this.showNotification(
                    this.language === 'fa' ? 'این ویدیو قبلاً حذف شده است' : 'This video has already been deleted',
                    'info'
                );
                return;
            }
            
            // Prevent opening video player for videos currently being deleted
            if (this.deletingVideos.has(filename)) {
                console.log('Video player modal blocked - video being deleted:', filename);
                this.showNotification(
                    this.language === 'fa' ? 'این ویدیو در حال حذف شدن است' : 'This video is being deleted',
                    'warning'
                );
                return;
            }
            
            // Check if video player modal is already open
            const existingModal = document.getElementById('videoPlayerModal');
            if (existingModal && existingModal.classList.contains('show')) {
                console.log('Video player modal already open, skipping duplicate open');
                return;
            }
            
            // Update modal title
            const titleElement = document.getElementById('videoPlayerTitle');
            if (titleElement) {
                titleElement.textContent = this.language === 'fa'
                    ? `ویدئو: ${timestamp}${weekday ? ' - ' + weekday : ''}`
                    : `Video: ${timestamp}${weekday ? ' - ' + weekday : ''}`;
            }
            
            // Update filename and timestamp
            const filenameElement = document.getElementById('videoFilename');
            const timestampElement = document.getElementById('videoTimestamp');
            
            if (filenameElement) {
                filenameElement.textContent = filename;
            }
            
            if (timestampElement) {
                timestampElement.textContent = timestamp;
            }
            
            // Setup modal button event handlers
            this.setupVideoPlayerModalButtons(url, filename);
            
            // Load video into player
            if (window.videoPlayer && !this.isDeletingVideo) {
                window.videoPlayer.loadVideo(url, filename);
            } else if (this.isDeletingVideo) {
                console.log('Video loading blocked - video deletion in progress');
                return;
            }
            
            // Show video player modal with proper configuration
            const modalEl = document.getElementById('videoPlayerModal');
            if (modalEl && !this.isDeletingVideo) {
                // Destroy existing modal instance if any
                const existingModal = bootstrap.Modal.getInstance(modalEl);
                if (existingModal) {
                    existingModal.dispose();
                }
                
                const modal = new bootstrap.Modal(modalEl, {
                    backdrop: true,
                    keyboard: true,
                    focus: true,
                    show: true
                });
                
                // Store modal instance for cleanup
                modalEl._modalInstance = modal;
                
                modal.show();
                
                // Ensure proper cleanup when modal is hidden
                modalEl.addEventListener('hidden.bs.modal', () => {
                    if (window.videoPlayer) {
                        window.videoPlayer.stopUpdateInterval();
                        if (window.videoPlayer.video) {
                            window.videoPlayer.video.pause();
                            window.videoPlayer.video.currentTime = 0;
                            // Additional cleanup to ensure video is completely stopped
                            try {
                                window.videoPlayer.video.src = '';
                                window.videoPlayer.video.load();
                            } catch (e) {
                                console.warn('Error during video cleanup:', e);
                            }
                        }
                    }
                }, { once: true });
            }
            
            console.log(`Video player opened for: ${filename}`);
            
        } catch (error) {
            console.error('Error showing video player:', error);
            this.showNotification(this.getTranslation('galleryError'), 'error');
        }
    }
    
    // Setup video player modal button event handlers
    setupVideoPlayerModalButtons(url, filename) {
        try {
            // Download button
            const downloadBtn = document.getElementById('downloadVideoBtn');
            if (downloadBtn) {
                const downloadHandler = (e) => {
                    e.preventDefault();
                    this.downloadVideo(url, filename);
                };
                
                // Remove existing listener if any
                downloadBtn.removeEventListener('click', downloadHandler);
                downloadBtn.addEventListener('click', downloadHandler);
            }
            
            // Delete button
            const deleteBtn = document.getElementById('deleteVideoBtn');
            if (deleteBtn) {
                // Capture filename in closure to prevent corruption
                const videoFilename = filename;
                
                const deleteHandler = (e) => {
                    e.preventDefault();
                    
                    console.log(`Video player modal delete button clicked for: ${videoFilename}`);
                    
                    // Prevent multiple confirmations if video is already being deleted
                    if (this.deletingVideos.has(videoFilename)) {
                        console.log(`Video ${videoFilename} is already being deleted, skipping confirmation`);
                        return;
                    }
                    
                    // Prevent deletion of already deleted videos
                    if (this.deletedVideos.has(videoFilename)) {
                        console.log(`Video ${videoFilename} has already been deleted, skipping confirmation`);
                        this.showNotification(
                            this.language === 'fa' ? 'این ویدیو قبلاً حذف شده است' : 'This video has already been deleted',
                            'info'
                        );
                        return;
                    }
                    
                    // Disable button temporarily to prevent multiple clicks
                    deleteBtn.disabled = true;
                    deleteBtn.style.opacity = '0.6';
                    
                    // Store the filename in a data attribute for verification
                    deleteBtn.setAttribute('data-deleting-filename', videoFilename);
                    
                    if (confirm(this.language === 'fa' ? 'آیا از حذف این ویدیو اطمینان دارید؟' : 'Are you sure you want to delete this video?')) {
                        // Verify filename hasn't changed
                        const currentFilename = deleteBtn.getAttribute('data-deleting-filename');
                        if (currentFilename === videoFilename) {
                            console.log(`Proceeding with deletion from video player modal: ${videoFilename}`);
                            this.deleteVideo(videoFilename);
                            // Modal will be closed automatically by deleteVideo function
                        } else {
                            console.error(`Filename mismatch in video player modal! Expected: ${videoFilename}, Got: ${currentFilename}`);
                            this.showNotification(
                                this.language === 'fa' ? 'خطا: نام فایل تغییر کرده است' : 'Error: Filename has changed',
                                'error'
                            );
                        }
                    } else {
                        // Re-enable button if user cancels
                        deleteBtn.disabled = false;
                        deleteBtn.style.opacity = '1';
                        deleteBtn.removeAttribute('data-deleting-filename');
                    }
                };
                
                // Remove existing listener if any
                deleteBtn.removeEventListener('click', deleteHandler);
                deleteBtn.addEventListener('click', deleteHandler);
            }
            
        } catch (error) {
            console.error('Error setting up video player modal buttons:', error);
        }
    }
    
    // Show Image Modal
    showImageModal(url, timestamp, weekday) {
        try {
            // Update modal title
            const titleElement = document.getElementById('imageModalLabel');
            if (titleElement) {
                titleElement.textContent = this.language === 'fa'
                    ? `تصویر: ${timestamp}${weekday ? ' - ' + weekday : ''}`
                    : `Image: ${timestamp}${weekday ? ' - ' + weekday : ''}`;
            }
            
            // Update image source
            const imageElement = document.getElementById('modalImage');
            if (imageElement) {
                imageElement.src = url;
            }
            
            // Setup modal button event handlers
            this.setupImageModalButtons(url);
            
            // Show image modal
            const modalEl = document.getElementById('imageModal');
            if (modalEl) {
                const modal = new bootstrap.Modal(modalEl, {
                    backdrop: true,
                    keyboard: true,
                    focus: true
                });
                modal.show();
            }
            
            console.log(`Image modal opened for: ${url}`);
            
        } catch (error) {
            console.error('Error showing image modal:', error);
            this.showNotification(this.getTranslation('galleryError'), 'error');
        }
    }
    
    // Setup image modal button event handlers
    setupImageModalButtons(url) {
        try {
            // Download button
            const downloadBtn = document.querySelector('#imageModal .btn-success');
            if (downloadBtn) {
                const downloadHandler = (e) => {
                    e.preventDefault();
                    // Extract filename from URL
                    const filename = url.split('/').pop() || 'image.jpg';
                    this.downloadImage(url, filename);
                };
                
                // Remove existing listener if any
                downloadBtn.removeEventListener('click', downloadHandler);
                downloadBtn.addEventListener('click', downloadHandler);
            }
            
            // Delete button
            const deleteBtn = document.querySelector('#imageModal .btn-danger');
            if (deleteBtn) {
                const deleteHandler = (e) => {
                    e.preventDefault();
                    // Extract filename from URL
                    const filename = url.split('/').pop() || 'image.jpg';
                    
                    // Check if photo is already being deleted
                    if (this.deletingPhotos && this.deletingPhotos.has(filename)) {
                        console.log(`Photo ${filename} is already being deleted, skipping action`);
                        return;
                    }
                    
                    if (confirm(this.language === 'fa' ? 'آیا از حذف این تصویر اطمینان دارید؟' : 'Are you sure you want to delete this image?')) {
                        // Close modal immediately
                        const modalEl = document.getElementById('imageModal');
                        if (modalEl) {
                            const modal = bootstrap.Modal.getInstance(modalEl);
                            if (modal) {
                                modal.hide();
                            }
                        }
                        // Remove backdrop to prevent black overlay
                        this.removeModalBackdrop();
                        // Start deletion process
                        this.deletePhoto(filename);
                    }
                };
                
                // Remove existing listener if any
                deleteBtn.removeEventListener('click', deleteHandler);
                deleteBtn.addEventListener('click', deleteHandler);
            }
            
        } catch (error) {
            console.error('Error setting up image modal buttons:', error);
        }
    }



















    // Cleanup object URLs
    cleanupObjectUrls() {
        try {
            this.objectUrls.forEach(url => {
                try {
                    URL.revokeObjectURL(url);
                } catch (e) {
                    console.warn('Error revoking object URL:', e);
                }
            });
            this.objectUrls.clear();
            console.log('Object URLs cleaned up');
        } catch (error) {
            console.warn('Error cleaning up object URLs:', error);
        }
    }

    // Download image
    downloadImage(imageUrl, filename) {
        try {
            // Create a temporary link element for download
            const link = document.createElement('a');
            link.href = imageUrl;
            link.download = filename;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            
            // Trigger download
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showNotification(
                this.language === 'fa' ? 'دانلود تصویر شروع شد' : 'Image download started',
                'success'
            );
            
        } catch (error) {
            console.error('Error downloading image:', error);
            this.showNotification(
                this.language === 'fa' ? 'خطا در دانلود تصویر' : 'Error downloading image',
                'error'
            );
        }
    }

    // Download video
    downloadVideo(videoUrl, filename) {
        try {
            // Create a temporary link element for download
            const link = document.createElement('a');
            link.href = videoUrl;
            link.download = filename;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            
            // Trigger download
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showNotification(
                this.language === 'fa' ? 'دانلود ویدیو شروع شد' : 'Video download started',
                'success'
            );
            
        } catch (error) {
            console.error('Error downloading video:', error);
            this.showNotification(
                this.language === 'fa' ? 'خطا در دانلود ویدیو' : 'Error downloading video',
                'error'
            );
        }
    }

    // Enhanced video deletion with proper cleanup and duplicate prevention
    async deleteVideo(filename) {
        // Validate filename parameter
        if (!filename || typeof filename !== 'string') {
            console.error('Invalid filename provided for deletion:', filename);
            this.showNotification(
                this.language === 'fa' ? 'خطا: نام فایل نامعتبر' : 'Error: Invalid filename',
                'error'
            );
            return;
        }
        
        // Prevent duplicate deletion requests - check this FIRST
        if (this.deletingVideos.has(filename)) {
            console.log(`Video ${filename} is already being deleted, skipping duplicate request`);
            return;
        }
        
        // Prevent deletion of already deleted videos
        if (this.deletedVideos.has(filename)) {
            console.log(`Video ${filename} has already been deleted, skipping request`);
            this.showNotification(
                this.language === 'fa' ? 'این ویدیو قبلاً حذف شده است' : 'This video has already been deleted',
                'info'
            );
            return;
        }
        
        // Prevent deletion if system is busy or if video is already being deleted
        if (this.isSystemBusy || this.deletingVideos.has(filename)) {
            console.log(`System busy or video ${filename} already being deleted, deferring request`);
            this.showNotification(
                this.language === 'fa' ? 'سیستم مشغول است، لطفاً صبر کنید' : 'System is busy, please wait',
                'warning'
            );
            return;
        }
        
        try {
            // Mark system as busy and video as being deleted IMMEDIATELY
            this.isSystemBusy = true;
            this.isDeletingVideo = true;
            this.deletingVideos.add(filename);
            
            console.log(`Starting deletion process for video: ${filename}`);
            
            // STEP 1: Clean up video player state BEFORE closing modals
            await this.cleanupVideoPlayerState(filename);
            
            // STEP 2: Close modals safely
            await this.closeModalsForVideo(filename);
            
            // STEP 3: Wait for modal cleanup to complete
            await new Promise(resolve => setTimeout(resolve, 300));
            
            // STEP 4: Clean up gallery elements
            await this.removeVideoFromGallery(filename);
            
            // STEP 5: Delete from server with timeout and better error handling
            console.log(`Sending delete request to server for: ${filename}`);
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            try {
                const response = await fetch(`/delete_video/${encodeURIComponent(filename)}`, {
                    method: 'POST',
                    headers: {
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0',
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    if (response.status === 401) {
                        throw new Error('Authentication failed. Please refresh the page and try again.');
                    }
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                // Check if response is JSON before parsing
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const responseText = await response.text();
                    console.error('Server returned non-JSON response:', responseText.substring(0, 200));
                    throw new Error('Server returned invalid response format. Please try again.');
                }
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    this.showNotification(data.message || 'ویدیو با موفقیت حذف شد', 'success');
                    
                    // Mark video as successfully deleted
                    this.deletedVideos.add(filename);
                    
                    // Refresh gallery to update pagination
                    this.currentVideoPage = 0;
                    // Add delay before refreshing to ensure deletion is complete
                    await new Promise(resolve => setTimeout(resolve, 500));
                    await this.loadVideos();
                    
                    console.log(`Video ${filename} deleted successfully`);
                } else {
                    throw new Error(data.message || 'خطا در حذف ویدیو');
                }
                
            } catch (fetchError) {
                clearTimeout(timeoutId);
                if (fetchError.name === 'AbortError') {
                    throw new Error('Deletion request timed out. The video might be very large.');
                }
                throw fetchError;
            }
            
        } catch (error) {
            console.error(`Error deleting video ${filename}:`, error);
            
            let errorMessage = this.language === 'fa' ? 'خطا در حذف ویدیو' : 'Error deleting video';
            
            if (error.message.includes('timeout')) {
                errorMessage = this.language === 'fa' ? 'حذف ویدیو زمان‌بر است. لطفاً صبر کنید.' : 'Video deletion is taking time. Please wait.';
            } else if (error.message.includes('large')) {
                errorMessage = this.language === 'fa' ? 'ویدیو بسیار بزرگ است. لطفاً صبر کنید.' : 'Video is very large. Please wait.';
            } else if (error.message.includes('invalid response format')) {
                errorMessage = this.language === 'fa' ? 'خطا در پاسخ سرور. لطفاً دوباره تلاش کنید.' : 'Server response error. Please try again.';
            }
            
            this.showNotification(errorMessage, 'error');
        } finally {
            // Always clean up deletion state
            this.deletingVideos.delete(filename);
            this.isSystemBusy = false;
            this.isDeletingVideo = false;
            this.reEnableDeleteButtons(filename);
            console.log(`Deletion process completed for: ${filename}`);
        }
    }

    // Remove video from gallery with animation and proper cleanup
    async removeVideoFromGallery(filename) {
        try {
            console.log(`Removing video from gallery: ${filename}`);
            
            const videosContainer = document.getElementById('videosContainer');
            if (!videosContainer) {
                console.warn('Videos container not found');
                return;
            }
            
            const videoItems = videosContainer.querySelectorAll('.gallery-item');
            let foundItems = 0;
            
            for (const item of videoItems) {
                if (item.dataset.filename === filename) {
                    foundItems++;
                    console.log(`Found gallery item for deletion: ${filename}`);
                    
                    // STEP 1: Clean up video element completely
                    const videoElement = item.querySelector('video');
                    if (videoElement) {
                        try {
                            // Pause and reset video
                            videoElement.pause();
                            videoElement.currentTime = 0;
                            videoElement.volume = 0;
                            videoElement.muted = true;
                            
                            // Remove all event listeners
                            videoElement.onloadstart = null;
                            videoElement.onloadedmetadata = null;
                            videoElement.oncanplay = null;
                            videoElement.onplay = null;
                            videoElement.onpause = null;
                            videoElement.onended = null;
                            videoElement.onerror = null;
                            videoElement.onabort = null;
                            videoElement.onstalled = null;
                            
                            // Clear video source
                            videoElement.src = '';
                            videoElement.load();
                            
                            console.log(`Gallery video element cleaned up for: ${filename}`);
                        } catch (e) {
                            console.warn('Error cleaning up gallery video element:', e);
                        }
                    }
                    
                    // STEP 2: Remove any stored references
                    if (this.videoElements.has(videoElement)) {
                        this.videoElements.delete(videoElement);
                    }
                    
                    if (this.activeVideos.has(videoElement)) {
                        this.activeVideos.delete(videoElement);
                    }
                    
                    // STEP 3: Clean up event listeners
                    if (this.videoEventListeners.has(videoElement)) {
                        const listeners = this.videoEventListeners.get(videoElement);
                        Object.values(listeners).forEach(listener => {
                            try {
                                videoElement.removeEventListener('loadstart', listener);
                                videoElement.removeEventListener('loadedmetadata', listener);
                                videoElement.removeEventListener('canplay', listener);
                                videoElement.removeEventListener('error', listener);
                                videoElement.removeEventListener('abort', listener);
                                videoElement.removeEventListener('stalled', listener);
                            } catch (e) {
                                console.warn('Error removing video event listeners:', e);
                            }
                        });
                        this.videoEventListeners.delete(videoElement);
                    }
                    
                    // STEP 4: Animate removal
                    item.style.opacity = '0';
                    item.style.transform = 'scale(0.8)';
                    item.style.transition = 'all 0.3s ease';
                    
                    // STEP 5: Remove from DOM after animation
                    await new Promise(resolve => {
                        setTimeout(() => {
                            try {
                                if (item.parentNode) {
                                    item.parentNode.removeChild(item);
                                    console.log(`Gallery item removed from DOM: ${filename}`);
                                }
                            } catch (e) {
                                console.warn('Error removing gallery item from DOM:', e);
                            }
                            resolve();
                        }, 300);
                    });
                }
            }
            
            console.log(`Gallery cleanup completed for ${filename}. Found and removed ${foundItems} items.`);
            
        } catch (error) {
            console.error(`Error removing video from gallery: ${filename}`, error);
        }
    }

    async loadLogs() {
        try {
            // --- دریافت وضعیت منابع سرور و نمایش در پنل مهندسی‌شد ---
            const statusPanel = document.getElementById('serverStatusPanel');
            if (statusPanel) {
                try {
                    const res = await fetch('/get_status');
                    if (res.ok) {
                        const statusData = await res.json();
                        if (statusData.status === 'success' && statusData.data) {
                            const d = statusData.data;
                            // RAM
                            const ram = document.getElementById('status-ram-value');
                            if (ram) { ram.textContent = d.ram_percent !== null && d.ram_percent !== undefined ? d.ram_percent + '%' : '--'; ram.className = 'status-value ' + (d.ram_percent < 70 ? 'status-success' : d.ram_percent < 90 ? 'status-warning' : 'status-error'); ram.setAttribute('data-key-label', 'ramLabel'); }
                            // CPU
                            const cpu = document.getElementById('status-cpu-value');
                            if (cpu) { cpu.textContent = d.cpu_percent !== null && d.cpu_percent !== undefined ? d.cpu_percent + '%' : '--'; cpu.className = 'status-value ' + (d.cpu_percent < 70 ? 'status-success' : d.cpu_percent < 90 ? 'status-warning' : 'status-error'); cpu.setAttribute('data-key-label', 'cpuLabel'); }
                            // Storage
                            const storage = document.getElementById('status-storage-value');
                            if (storage) { storage.textContent = d.storage || '--'; storage.className = 'status-value ' + (parseFloat((d.storage||'0').replace('%','')) > 20 ? 'status-success' : 'status-warning'); storage.setAttribute('data-key-label', 'storageLabel'); }
                            // Internet
                            const internet = document.getElementById('status-internet-value');
                            if (internet) { internet.textContent = d.internet === 'online' ? (this.language === 'fa' ? 'آنلاین' : 'Online') : (this.language === 'fa' ? 'آفلاین' : 'Offline'); internet.className = 'status-value ' + (d.internet === 'online' ? 'status-success' : 'status-error'); internet.setAttribute('data-key-label', 'internetLabel'); }
                            // Camera
                            const camera = document.getElementById('status-camera-value');
                            if (camera) { camera.textContent = d.camera_status === 'online' ? (this.language === 'fa' ? 'آنلاین' : 'Online') : (this.language === 'fa' ? 'آفلاین' : 'Offline'); camera.className = 'status-value ' + (d.camera_status === 'online' ? 'status-success' : 'status-error'); camera.setAttribute('data-key-label', 'cameraLabel'); }
                            // Pico
                            const pico = document.getElementById('status-pico-value');
                            if (pico) { pico.textContent = d.pico_status === 'online' ? (this.language === 'fa' ? 'آنلاین' : 'Online') : (this.language === 'fa' ? 'آفلاین' : 'Offline'); pico.className = 'status-value ' + (d.pico_status === 'online' ? 'status-success' : 'status-error'); pico.setAttribute('data-key-label', 'picoLabel'); }
                        }
                    }
                } catch (e) { /* ignore */ }
            }
            // --- بارگذاری لاگ‌ها ---
            const logLimit = document.getElementById('logLimit')?.value || 50;
            const response = await fetch(`/get_logs?limit=${logLimit}`);
            if (!response.ok) throw new Error('Failed to fetch logs');
            const data = await response.json();

            const logsContainer = document.getElementById('logsContainer');
            if (!logsContainer) return;

            logsContainer.innerHTML = '';
            // حذف لاگ‌های تکراری بر اساس message+timestamp+level
            const uniqueLogs = [];
            const seen = new Set();
            data.logs.forEach(log => {
                const key = `${log.message}|${log.timestamp}|${log.level}`;
                if (!seen.has(key)) {
                    uniqueLogs.push(log);
                    seen.add(key);
                }
            });
            uniqueLogs.forEach(log => {
                const logItem = document.createElement('div');
                logItem.className = `log-card log-level-${log.level ? log.level.toLowerCase() : 'info'}`;
                // آیکون سطح لاگ
                let icon = 'fa-info-circle';
                let levelKey = log.level ? log.level.toLowerCase() : 'info';
                // Fallback for Persian log levels in English mode
                if (this.language === 'en') {
                    const faToEn = {
                        'دستور': 'command',
                        'عکس': 'photo',
                        'حذف': 'delete',
                        'خطا': 'error',
                        'اطلاعات': 'info',
                        'هشدار': 'warning',
                        'اتصال': 'connection',
                        'ویدئو': 'video',
                        'پشتیبان': 'backup',
                        'حرکت': 'motion',
                        'خروج': 'logout',
                    };
                    if (faToEn[levelKey]) levelKey = faToEn[levelKey];
                }
                if (levelKey === 'error') icon = 'fa-times-circle';
                else if (levelKey === 'warning') icon = 'fa-exclamation-triangle';
                else if (levelKey === 'command') icon = 'fa-terminal';
                else if (levelKey === 'photo') icon = 'fa-camera';
                else if (levelKey === 'delete') icon = 'fa-trash';
                else if (levelKey === 'logout') icon = 'fa-sign-out-alt';
                // --- Show source and pico_timestamp clearly ---
                let detailsHtml = '';
                let sourceVal = log.source;
                if (log.source) {
                    detailsHtml += `<div class="log-detail"><span class="log-detail-key">${this.getTranslation('source', this.language === 'fa' ? 'منبع' : 'Source')}:</span> <span class="log-detail-value">${sourceVal}</span></div>`;
                }
                if (log.pico_timestamp) {
                    detailsHtml += `<div class="log-detail"><span class="log-detail-key">${this.getTranslation('picoTime', this.language === 'fa' ? 'زمان Pico' : 'Pico Time')}:</span> <span class="log-detail-value">${log.pico_timestamp}</span></div>`;
                }
                // Other details (if any)
                detailsHtml += Object.keys(log)
                    .filter(k => !['timestamp','level','message','source','pico_timestamp'].includes(k))
                    .map(k => `<div class="log-detail"><span class="log-detail-key">${this.getTranslation(k, k)}</span>: <span class="log-detail-value">${log[k]}</span></div>`).join('');
                logItem.innerHTML = `
                    <div class="log-card-header">
                        <i class="fas ${icon} log-icon"></i>
                        <span class="log-level-label">${this.getTranslation('logLevel_' + levelKey, this.language === 'fa' ? this.translateLogLevel(log.level) : levelKey.charAt(0).toUpperCase() + levelKey.slice(1))}</span>
                        <span class="log-time">${new Date(log.timestamp).toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US')}</span>
                    </div>
                    <div class="log-message">${log.message}</div>
                    ${detailsHtml}
                `;
                logsContainer.appendChild(logItem);
            });

            // --- ترجمه labelها و valueها بعد از رندر ---
            this.translateLogDetailLabels();
            this.translateStatusLabels();
            this.translateLogLevelLabels();

            this.showNotification(this.getTranslation('logsUpdated'), 'success');
        } catch (error) {
            this.showNotification(this.getTranslation('connectionError'), 'error', {
                title: this.getTranslation('connectionError'),
                message: error.message,
                code: error.code || '-',
                source: 'fetch(/get_logs)'
            });
        }
    }

    async showAllLogs() {
        try {
            const response = await fetch('/get_all_logs');
            if (!response.ok) throw new Error('Failed to fetch all logs');
            const data = await response.json();

            const allLogsContainer = document.getElementById('allLogsContainer');
            if (!allLogsContainer) return;

            allLogsContainer.innerHTML = '';
            data.logs.forEach(log => {
                const logItem = document.createElement('div');
                let levelKey = log.level ? log.level.toLowerCase() : 'info';
                if (this.language === 'en') {
                    const faToEn = {
                        'دستور': 'command',
                        'عکس': 'photo',
                        'حذف': 'delete',
                        'خطا': 'error',
                        'اطلاعات': 'info',
                        'هشدار': 'warning',
                        'اتصال': 'connection',
                        'ویدئو': 'video',
                        'پشتیبان': 'backup',
                        'حرکت': 'motion',
                        'خروج': 'logout',
                    };
                    if (faToEn[levelKey]) levelKey = faToEn[levelKey];
                }
                logItem.className = `log-item log-level-${levelKey}`;
                logItem.innerHTML = `
                    <span class="log-time">${new Date(log.timestamp).toLocaleString(this.language === 'fa' ? 'fa-IR' : 'en-US')}</span>
                    <span class="log-level ${levelKey}">${this.language === 'fa' ? this.translateLogLevel(log.level) : this.getTranslation('logLevel_' + levelKey)}</span>
                    <span class="log-message">${this.getTranslation('logMsg_' + (log.code || levelKey), log.message)}</span>
                `;
                allLogsContainer.appendChild(logItem);
            });

            // Remove emoji from button text (if present)
            const showAllLogsBtn = document.getElementById('showAllLogsBtn');
            if (showAllLogsBtn) {
                showAllLogsBtn.innerHTML = this.language === 'fa' ? 'نمایش همه گزارش‌ها' : 'Show all logs';
            }
            const refreshLogsBtn = document.getElementById('refreshLogsBtn');
            if (refreshLogsBtn) {
                refreshLogsBtn.innerHTML = this.language === 'fa' ? 'به‌روزرسانی گزارش‌ها' : 'Refresh logs';
            }

            const modal = new bootstrap.Modal(document.getElementById('allLogsModal'));
            const modalEl = document.getElementById('allLogsModal');
            // Clean up overlays on close
            modalEl.removeEventListener('hidden.bs.modal', window._allLogsModalCleanup);
            window._allLogsModalCleanup = function() {
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            };
            modalEl.addEventListener('hidden.bs.modal', window._allLogsModalCleanup);
            modal.show();
        } catch (error) {
            this.showNotification(this.getTranslation('connectionError'), 'error', {
                title: this.getTranslation('connectionError'),
                message: error.message,
                code: error.code || '-',
                source: 'fetch(/get_all_logs)'
            });
        }
    }

    translateLogLevel(level) {
        const translations = {
            fa: {
                info: 'اطلاعات',
                error: 'خطا',
                warning: 'هشدار',
                connection: 'اتصال',
                command: 'دستور',
                photo: 'عکس',
                video: 'ویدئو',
                backup: 'پشتیبان',
                delete: 'حذف',
                motion: 'حرکت'
            },
            en: {
                info: 'Information',
                error: 'Error',
                warning: 'Warning',
                connection: 'Connection',
                command: 'Command',
                photo: 'Photo',
                video: 'Video',
                backup: 'Backup',
                delete: 'Delete',
                motion: 'Motion'
            }
        };
        
        const lang = this.language || 'fa';
        return translations[lang]?.[level.toLowerCase()] || level;
    }

    toggleTheme() {
        try {
            const isDark = document.body.classList.toggle('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            this.applySettingsToUI({
                theme: isDark ? 'dark' : 'light',
                language: this.language || localStorage.getItem('language') || 'fa',
                flashSettings: localStorage.getItem('flashSettings') || '{"intensity":50,"enabled":false}',
                servo1: localStorage.getItem('servo1') || 90,
                servo2: localStorage.getItem('servo2') || 90,
                device_mode: localStorage.getItem('device_mode') || 'desktop'
            });
            this.saveUserSettingsToServer();
            this.updateFooterThemeBtn();
        } catch (error) {
            console.error('خطا در تغییر تم:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    updateFooterThemeBtn() {
        const btn = document.getElementById('footerThemeBtn');
        if (!btn) return;
        const icon = btn.querySelector('i');
        const span = btn.querySelector('span[data-key="themeLight"]');
        const isDark = document.body.classList.contains('dark-mode');
        if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        if (span) span.textContent = this.getTranslation(isDark ? 'themeLight' : 'themeDark');
    }

    async toggleLanguage() {
        try {
            this.language = this.language === 'fa' ? 'en' : 'fa';
            localStorage.setItem('language', this.language);
            fetch('/set_language', {
                method: 'POST',
                body: JSON.stringify({ lang: this.language })
            }).then(async res => {
                if (res.ok) {
                    const data = await res.json();
                    if (data.language) this.language = data.language;
                    localStorage.setItem('language', this.language);
                    await this.updateLanguage(this.language);
                    this.saveUserSettingsToServer();
                }
            });
        } catch (error) {
            console.error('خطا در تغییر زبان:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    async updateLanguage(lang) {
        this.language = lang;
        localStorage.setItem('language', lang);
        document.body.classList.toggle('lang-fa', lang === 'fa');
        document.body.classList.toggle('lang-en', lang === 'en');
        document.body.classList.remove('rtl', 'ltr');
        document.body.classList.add(lang === 'fa' ? 'rtl' : 'ltr');
        document.documentElement.lang = lang;
        
        if (!window.translations || !window.translations[lang]) {
            try {
                const res = await fetch(`/get_translations?lang=${lang}`);
                if (res.ok) {
                    window.translations = window.translations || {};
                    window.translations[lang] = await res.json();
                }
            } catch (error) {
                console.warn('Error loading translations:', error);
            }
        }
        this.translations = window.translations[lang] || {};
        
        // Translate UI elements
        document.querySelectorAll('[data-key]').forEach(el => {
            const key = el.getAttribute('data-key');
            if (el.querySelector('i') && el.childNodes.length > 1) {
                let foundText = false;
                for (let i = 0; i < el.childNodes.length; i++) {
                    if (el.childNodes[i].nodeType === 3) {
                        el.childNodes[i].nodeValue = ' ' + this.getTranslation(key, el.childNodes[i].nodeValue.trim());
                        foundText = true;
                        break;
                    }
                }
                if (!foundText) {
                    el.appendChild(document.createTextNode(' ' + this.getTranslation(key)));
                }
            } else {
                el.textContent = this.getTranslation(key, el.textContent);
            }
        });
        
        document.querySelectorAll('[data-key-title]').forEach(el => {
            const key = el.getAttribute('data-key-title');
            el.setAttribute('title', this.getTranslation(key, el.getAttribute('title')));
        });
        
        document.querySelectorAll('[data-key-placeholder]').forEach(el => {
            const key = el.getAttribute('data-key-placeholder');
            el.setAttribute('placeholder', this.getTranslation(key, el.getAttribute('placeholder')));
        });
        
        document.querySelectorAll('[data-key-alt]').forEach(el => {
            const key = el.getAttribute('data-key-alt');
            el.setAttribute('alt', this.getTranslation(key, el.getAttribute('alt')));
        });
        
        // Run typewriters
        if (typeof runHeaderTypewriter === 'function') runHeaderTypewriter();
        if (typeof runFooterTypewriter === 'function') runFooterTypewriter();
        
        // Update UI state
        this.updateUIStateOnce();
        
        // Reload gallery and videos
        this.currentPage = 0;
        this.currentVideoPage = 0;
        await this.loadGallery();
        await this.loadVideos();
    }

    async logout() {
        try {
            localStorage.clear();
            sessionStorage.clear();
            
            try {
                const response = await fetch('/logout', { 
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    console.warn('Logout response not ok:', response.status);
                }
            } catch (fetchError) {
                console.warn('Logout fetch error (continuing anyway):', fetchError);
            }
            
            window.location.href = '/login';
            
        } catch (error) {
            console.error('خطا در خروج:', error);
            window.location.href = '/login';
        }
    }

    toggleMenu() {
        const nav = document.querySelector('.header-nav');
        if (nav) nav.classList.toggle('active');
    }

    updateConnectionStatus(connected) {
        const statusIcon = document.createElement('i');
        statusIcon.className = `fas fa-circle status-icon ${connected ? 'connected' : 'disconnected'}`;
        const existingIcon = document.querySelector('.status-indicator .status-icon');
        if (existingIcon) existingIcon.remove();
        const statusIndicator = document.querySelector('.status-indicator');
        if (statusIndicator) statusIndicator.appendChild(statusIcon);
    }

    updateSystemStatus(data) {
        const oldStatus = { ...this.systemStatus };
        
        this.systemStatus.server = data.server_status || 'offline';
        this.systemStatus.camera = data.camera_status || 'offline';
        this.systemStatus.pico = data.pico_status || 'offline';
        
        // Only log if status actually changed
        const hasChanged = JSON.stringify(oldStatus) !== JSON.stringify(this.systemStatus);
        if (hasChanged) {
            console.log('وضعیت سیستم به‌روزرسانی شد:', this.systemStatus);
        }
        
        this.updateStatusModal();
        
        if (data.device_status) {
            this.updateDeviceStatus(data.device_status);
        }
    }
    
    updateDeviceStatus(deviceStatus) {
        const oldDeviceStatus = this.lastDeviceStatus || {};
        const picoStatus = deviceStatus.pico?.online ? 'آنلاین' : 'آفلاین';
        const esp32camStatus = deviceStatus.esp32cam?.online ? 'آنلاین' : 'آفلاین';
        
        // Only log if device status actually changed
        const hasChanged = JSON.stringify(oldDeviceStatus) !== JSON.stringify(deviceStatus);
        if (hasChanged) {
            console.log('Device Status:', {
                pico: picoStatus,
                esp32cam: esp32camStatus,
                pico_errors: deviceStatus.pico?.errors?.length || 0,
                esp32cam_errors: deviceStatus.esp32cam?.errors?.length || 0
            });
        }
        
        // Store current status for comparison
        this.lastDeviceStatus = { ...deviceStatus };
        
        if (!deviceStatus.pico?.online) {
            this.showNotification('پیکو آفلاین است', 'warning');
        }
        if (!deviceStatus.esp32cam?.online) {
            this.showNotification('ESP32-CAM آفلاین است', 'warning');
        }
    }
    
    handleCriticalError(data) {
        console.error('Critical error received:', data);
        this.showNotification(`خطای بحرانی: ${data.message}`, 'error');
        
        this.showErrorModal({
            title: 'خطای بحرانی سیستم',
            message: data.message,
            source: data.source,
            timestamp: data.timestamp
        });
        
        this.logErrorToServer('critical_error', data);
    }
    
    async logErrorToServer(type, data) {
        try {
            await fetch('/api/v1/log_error', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: type,
                    data: data,
                    timestamp: new Date().toISOString(),
                    user_agent: navigator.userAgent
                })
            });
        } catch (error) {
            console.error('Failed to log error to server:', error);
        }
    }

    updateStatusModal() {
        const wsStatus = document.getElementById('wsStatus');
        const serverStatus = document.getElementById('serverStatus');
        const cameraStatus = document.getElementById('cameraStatus');
        const picoStatus = document.getElementById('picoStatus');
        const dbStatus = document.getElementById('dbStatus');
        const internetStatus = document.getElementById('internetStatus');
        const storageStatus = document.getElementById('storageStatus');
        // Helper to set class based on value
        function setStatusClass(el, status) {
            if (!el) return;
            el.classList.remove('status-success', 'status-error', 'status-warning');
            if (["connected","online","متصل","آنلاین"].includes(status)) el.classList.add('status-success');
            else if (["disconnected","offline","قطع","آفلاین","خاموش"].includes(status)) el.classList.add('status-error');
            else el.classList.add('status-warning');
        }
        if (wsStatus) {
            const val = this.language === 'fa' ? (this.systemStatus.websocket === 'connected' ? 'متصل' : 'قطع') : this.systemStatus.websocket;
            wsStatus.textContent = val;
            setStatusClass(wsStatus, this.systemStatus.websocket === 'connected' ? 'connected' : 'disconnected');
        }
        if (serverStatus) {
            const val = this.language === 'fa' ? (this.systemStatus.server === 'online' ? 'آنلاین' : 'آفلاین') : this.systemStatus.server;
            serverStatus.textContent = val;
            setStatusClass(serverStatus, this.systemStatus.server === 'online' ? 'online' : 'offline');
        }
        if (cameraStatus) {
            const val = this.language === 'fa' ? (this.systemStatus.camera === 'online' ? 'آنلاین' : 'آفلاین') : this.systemStatus.camera;
            cameraStatus.textContent = val;
            setStatusClass(cameraStatus, this.systemStatus.camera === 'online' ? 'online' : 'offline');
        }
        if (picoStatus) {
            const val = this.language === 'fa' ? (this.systemStatus.pico === 'online' ? 'آنلاین' : 'آفلاین') : this.systemStatus.pico;
            picoStatus.textContent = val;
            setStatusClass(picoStatus, this.systemStatus.pico === 'online' ? 'online' : 'offline');
        }
        if (dbStatus) {
            const val = this.systemStatus.db || (this.language === 'fa' ? 'نامشخص' : 'Unknown');
            dbStatus.textContent = val;
            setStatusClass(dbStatus, val);
        }
        if (internetStatus) {
            const val = this.systemStatus.internet || (this.language === 'fa' ? 'نامشخص' : 'Unknown');
            internetStatus.textContent = val;
            setStatusClass(internetStatus, val);
        }
        if (storageStatus) {
            const val = this.systemStatus.storage || (this.language === 'fa' ? 'نامشخص' : 'Unknown');
            storageStatus.textContent = val;
            setStatusClass(storageStatus, val);
        }
    }

    handleVideoFrame(frameData) {
        try {
            const video = document.getElementById('streamVideo');
            if (!video) {
                console.warn('[DEBUG] Stream video element not found');
                return;
            }
            
            if (!this.isStreaming) {
                console.log('[DEBUG] Not streaming, skipping frame update');
                return;
            }
            
            // Validate frame data
            if (!frameData || frameData.byteLength === 0) {
                console.warn('[DEBUG] Invalid frame data received');
                return;
            }
            
            // Clean up previous URL to prevent memory leaks
            const previousUrl = video.dataset.previousUrl;
            if (previousUrl) {
                URL.revokeObjectURL(previousUrl);
            }
            
            // Create blob URL from binary data
            const blob = new Blob([frameData], { type: 'image/jpeg' });
            const url = URL.createObjectURL(blob);
            
            // Update video source
            video.src = url;
            video.dataset.previousUrl = url;
            
            // Update frame statistics
            this.frameUpdateCount = (this.frameUpdateCount || 0) + 1;
            this.lastFrameTime = Date.now();
            
            // Log frame statistics every 100 frames
            if (this.frameUpdateCount % 100 === 0) {
                console.log(`[DEBUG] Video frame updated successfully - Total frames: ${this.frameUpdateCount}`);
                this.cleanupMemory();
            }
            
            // Update FPS display if available
            this.updateFPSDisplay();
            
        } catch (error) {
            console.error('[DEBUG] Error handling video frame:', error);
        }
    }
    
    updateFPSDisplay() {
        try {
            const fpsElement = document.getElementById('fpsDisplay');
            if (fpsElement && this.frameUpdateCount > 0) {
                const currentTime = Date.now();
                const timeDiff = (currentTime - (this.frameStartTime || currentTime)) / 1000;
                const fps = this.frameUpdateCount / timeDiff;
                fpsElement.textContent = `FPS: ${fps.toFixed(1)}`;
            }
        } catch (error) {
            console.warn('[DEBUG] Error updating FPS display:', error);
        }
    }

    updateStreamFrame(data, resolution) {
        try {
            const video = document.getElementById('streamVideo');
            if (!video) {
                console.warn('[DEBUG] Stream video element not found');
                return;
            }
            
            if (!this.isStreaming) {
                console.log('[DEBUG] Not streaming, skipping frame update');
                return;
            }
            
            // Validate data
            if (!data || typeof data !== 'string') {
                console.warn('[DEBUG] Invalid frame data received:', typeof data);
                return;
            }
            
            // Clean up previous URL to prevent memory leaks
            const previousUrl = video.dataset.previousUrl;
            if (previousUrl) {
                URL.revokeObjectURL(previousUrl);
            }
            
            // Create new URL with proper error handling
            let url;
            try {
                url = `data:image/jpeg;base64,${data}`;
            } catch (error) {
                console.error('[DEBUG] Error creating data URL:', error);
                return;
            }
            
            // Update video source
            video.src = url;
            video.dataset.previousUrl = url;
            
            // Update resolution if provided
            if (resolution && resolution.width && resolution.height) {
                const currentWidth = video.style.width;
                const currentHeight = video.style.height;
                const newWidth = `${resolution.width}px`;
                const newHeight = `${resolution.height}px`;
                
                // Only update if changed
                if (currentWidth !== newWidth || currentHeight !== newHeight) {
                    video.style.width = newWidth;
                    video.style.height = newHeight;
                    console.log(`[DEBUG] Updated video resolution to ${newWidth}x${newHeight}`);
                }
            }
            
            // Clean up URL after a delay to prevent memory leaks
            setTimeout(() => {
                if (video.dataset.previousUrl === url && video.src !== url) {
                    URL.revokeObjectURL(url);
                    delete video.dataset.previousUrl;
                }
            }, 2000); // Reduced to 2 seconds for better performance
            
            // Memory optimization
            if (this.frameUpdateCount % 100 === 0) {  // Every 100 frames
                this.cleanupMemory();
            }
            this.frameUpdateCount = (this.frameUpdateCount || 0) + 1;
            
            console.log('[DEBUG] Frame updated successfully');
            
        } catch (error) {
            console.error('[DEBUG] Error updating stream frame:', error);
        }
    }
    
    cleanupMemory() {
        try {
            // اجرای garbage collection در صورت امکان
            if (window.gc) {
                window.gc();
            }
            
            // پاک کردن cache اضافی
            if ('caches' in window) {
                caches.keys().then(names => {
                    names.forEach(name => {
                        if (name.includes('image') || name.includes('video')) {
                            caches.delete(name);
                        }
                    });
                }).catch(e => {
                    console.warn('Error cleaning caches:', e);
                });
            }
            
            // پاک کردن object URLs اضافی
            if (this.objectUrls) {
                this.objectUrls.forEach(url => {
                    try {
                        URL.revokeObjectURL(url);
                    } catch (e) {
                        console.warn('Error revoking URL:', e);
                    }
                });
                this.objectUrls = [];
            }
            
            // پاک کردن event listeners اضافی
            if (this.cleanupCallbacks) {
                this.cleanupCallbacks.forEach(callback => {
                    try {
                        callback();
                    } catch (e) {
                        console.warn('Error in cleanup callback:', e);
                    }
                });
            }
            
            // پاک کردن video elements اضافی
            const videos = document.querySelectorAll('video');
            videos.forEach(video => {
                if (video.src && video.src.startsWith('blob:')) {
                    try {
                        URL.revokeObjectURL(video.src);
                        video.removeAttribute('src');
                        video.load();
                    } catch (e) {
                        console.warn('Error cleaning up video:', e);
                    }
                }
            });
            
            // پاک کردن image elements اضافی
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                if (img.src && img.src.startsWith('blob:')) {
                    try {
                        URL.revokeObjectURL(img.src);
                    } catch (e) {
                        console.warn('Error cleaning up image:', e);
                    }
                }
            });
            
            // پاک کردن WebSocket connections اضافی
            if (this.ws && this.ws.readyState === WebSocket.CLOSED) {
                this.ws = null;
            }
            
            // پاک کردن fetch requests اضافی
            if (window.activeRequests) {
                for (const [key, controller] of window.activeRequests.entries()) {
                    try {
                        controller.abort();
                    } catch (e) {
                        console.warn('Error aborting request:', e);
                    }
                }
                window.activeRequests.clear();
            }
            
            // پاک کردن timeouts اضافی
            if (this.cleanupTimeouts) {
                this.cleanupTimeouts.forEach(timeoutId => {
                    try {
                        clearTimeout(timeoutId);
                    } catch (e) {
                        console.warn('Error clearing timeout:', e);
                    }
                });
                this.cleanupTimeouts = [];
            }
            
            // پاک کردن intervals اضافی
            if (this.cleanupIntervals) {
                this.cleanupIntervals.forEach(intervalId => {
                    try {
                        clearInterval(intervalId);
                    } catch (e) {
                        console.warn('Error clearing interval:', e);
                    }
                });
                this.cleanupIntervals = [];
            }
            
        } catch (error) {
            console.warn('خطا در پاک‌سازی حافظه:', error);
        }
    }

    handlePhotoCaptured(data) {
        this.showNotification(this.getTranslation('photoCaptured'), 'success');
        this.currentPage = 0;
        document.getElementById('galleryContainer').innerHTML = '';
        this.loadGallery();
    }

    handleVideoCreated(data) {
        this.showNotification(this.language === 'fa' ? 'ویدئو جدید ایجاد شد' : 'New video created', 'success');
        // بازنشانی گالری ویدیوها
        this.currentVideoPage = 0;
        const videosContainer = document.getElementById('videosContainer');
        if (videosContainer) {
            videosContainer.innerHTML = '';
            this.loadVideos();
        }
    }

    async loadInitialData() {
        try {
            await Promise.all([this.loadGallery(), this.loadVideos()]); // حذف loadLogs از اینجا
        } catch (error) {
            console.error('خطا در بارگذاری داده‌های اولیه:', error);
            this.showNotification(this.getTranslation('connectionError'), 'error');
        }
    }

    startStatusUpdates() {
        // Start periodic status updates
        this.statusUpdateInterval = setInterval(async () => {
            try {
                const response = await fetch('/get_status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(this.csrfToken ? {'X-CSRF-Token': this.csrfToken} : {})
                    },
                    credentials: 'include'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'success' && data.data) {
                        this.updateSystemStatus(data.data);
                    }
                }
            } catch (error) {
                console.warn('Status update error:', error);
            }
        }, 60000); // Update every 60 seconds
    }

    // Enhanced cleanup method
    cleanup() {
        console.log('Enhanced cleanup started...');
        
        try {
            // Clear intervals
            if (this.statusUpdateInterval) {
                clearInterval(this.statusUpdateInterval);
                this.statusUpdateInterval = null;
            }
            
            // Close WebSocket
            if (this.websocket) {
                this.websocket.close();
                this.websocket = null;
            }
            
            // Clean up all videos
            this.cleanupAllVideos();
            
            // Clean up callbacks
            if (this.cleanupCallbacks && this.cleanupCallbacks.length > 0) {
                this.cleanupCallbacks.forEach(callback => {
                    try {
                        callback();
                    } catch (e) {
                        console.warn('Error in cleanup callback:', e);
                    }
                });
                this.cleanupCallbacks = [];
            }
            
            // Clear all tracking data
            this.videoCache.clear();
            this.activeVideos.clear();
            this.videoElements = new WeakMap();
            this.videoEventListeners.clear();
            this.objectUrls.clear();
            
            // Reset modal state
            this.modalState = {
                isOpen: false,
                currentVideo: null,
                currentImage: null
            };
            
            console.log('Enhanced cleanup completed');
            
        } catch (error) {
            console.error('Error during enhanced cleanup:', error);
        }
    }

    // Enhanced cleanup for all videos
    cleanupAllVideos() {
        console.log('Enhanced cleanup for all videos started...');
        
        try {
            // Clean up gallery videos
            const videosContainer = document.getElementById('videosContainer');
            if (videosContainer) {
                const galleryVideos = videosContainer.querySelectorAll('video');
                galleryVideos.forEach(video => {
                    this.cleanupVideoElement(video);
                });
            }
            
            // Clean up modal video
            const modalVideo = document.getElementById('modalVideo');
            if (modalVideo) {
                this.cleanupModalVideo(modalVideo);
            }
            
            // Close any open modals
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                try {
                    const modal = bootstrap.Modal.getInstance(openModal);
                    if (modal) modal.hide();
                } catch (e) {
                    console.warn('Error closing modal:', e);
                }
            }
            
            // Clean up object URLs
            this.cleanupObjectUrls();
            
            // Reset modal state
            this.modalState.isOpen = false;
            this.modalState.currentVideo = null;
            this.modalState.currentImage = null;
            
            // Clear video cache
            this.videoCache.clear();
            
            // Clear active videos set
            this.activeVideos.clear();
            
            // Clear video elements map
            this.videoElements = new WeakMap();
            
            console.log('Enhanced video cleanup completed');
            
        } catch (error) {
            console.error('Error during enhanced video cleanup:', error);
        }
    }

    // Setup page refresh and unload handling to prevent unwanted video downloads
    setupPageRefreshHandling() {
        // Handle page refresh
        window.addEventListener('beforeunload', (e) => {
            console.log('Page refresh detected, cleaning up videos...');
            this.cleanupAllVideos();
            
            // Show confirmation dialog only if videos are playing
            const playingVideos = document.querySelectorAll('video[src]:not([src=""])');
            if (playingVideos.length > 0) {
                e.preventDefault();
                e.returnValue = 'Videos are playing. Are you sure you want to leave?';
                return e.returnValue;
            }
        });

        // Handle page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Page hidden, pausing all videos...');
                this.pauseAllVideos();
            }
        });

        // Handle page focus/blur
        window.addEventListener('blur', () => {
            console.log('Page lost focus, pausing all videos...');
            this.pauseAllVideos();
        });

        // Handle browser back/forward
        window.addEventListener('popstate', () => {
            console.log('Navigation detected, cleaning up videos...');
            this.cleanupAllVideos();
        });
    }

    // Pause all videos without cleaning them up
    pauseAllVideos() {
        const allVideos = document.querySelectorAll('video');
        allVideos.forEach(video => {
            try {
                if (!video.paused) {
                    video.pause();
                }
            } catch (e) {
                console.warn('Error pausing video:', e);
            }
        });
    }

    // Update UI state once to prevent multiple updates
    updateUIStateOnce() {
        // Update stream button state
        this.updateStreamButton();
        
        // Update device mode button
        this.updateDeviceModeButton();
        
        // Update theme button
        this.updateFooterThemeBtn();
        
        // Update language button
        const langIcon = document.querySelector('#languageToggle i');
        if (langIcon) {
            langIcon.classList.remove('lang-rotate-rtl', 'lang-rotate-ltr');
            if (this.language === 'fa') langIcon.classList.add('lang-rotate-rtl');
            else langIcon.classList.add('lang-rotate-ltr');
        }
        
        // Update smart motion toggles
        if (typeof updateSmartMotionToggles === 'function') {
            updateSmartMotionToggles();
        }
    }

    loadMorePhotos() {
        this.loadGallery();
    }

    loadMoreVideos() {
        if (!this.isLoading) {
            this.loadVideos();
        }
    }

    showNotification(messageKey, type, details) {
        const message = this.getTranslation(messageKey, messageKey);
        if (window.isReloading || document.readyState !== 'complete' || !window.system || !window.system.websocket) return;
        if (type === 'error' && this.websocket && this.websocket.readyState === 1) {
            return;
        }
        if (type === 'error') {
            if (this.activeErrorNotification) return;
        }
        document.querySelectorAll('.notification.notification-' + type).forEach(n => n.remove());
        let extraInfo = '';
        if (type === 'error') {
            const now = new Date();
            extraInfo += `<div style='font-size:0.92em;margin-top:4px;'><b>⏰ زمان:</b> ${now.toLocaleString('fa-IR')}<br/>`;
            extraInfo += `<b>WebSocket:</b> ${this.websocket ? this.websocket.readyState : 'N/A'}<br/>`;
            extraInfo += `<b>navigator.onLine:</b> ${navigator.onLine ? 'آنلاین' : 'آفلاین'}<br/>`;
            if (details && details.event) {
                extraInfo += `<b>event.type:</b> ${details.event.type || '-'}<br/>`;
                extraInfo += `<b>event:</b> ${JSON.stringify(details.event)}<br/>`;
            }
            if (details && details.stack) {
                extraInfo += `<b>Stack:</b> <pre style='white-space:pre-wrap;direction:ltr;'>${details.stack}</pre>`;
            }
            extraInfo += `</div>`;
        }
        if (type === 'error' && details) {
            this.showErrorModal(details);
        }
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} animate__animated animate__fadeIn`;
        notification.innerHTML = `
            <span>${message}</span>
            ${extraInfo}
            <button class="notification-close"><i class="fas fa-times"></i></button>
        `;
        document.body.appendChild(notification);
        if (type === 'error') {
            this.activeErrorNotification = notification;
        }
        notification.querySelector('.notification-close').onclick = () => {
                notification.remove();
            if (type === 'error') this.activeErrorNotification = null;
        };
            setTimeout(() => {
            notification.classList.add('animate__fadeOut');
            setTimeout(() => notification.remove(), 500);
        }, 4000);
    }

    showErrorModal(details) {
        let modal = document.getElementById('errorModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = 'errorModal';
            modal.tabIndex = -1;
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i> ${this.getTranslation('connectionError')}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-2"><b>${this.language === 'fa' ? 'منبع' : 'Source'}:</b> ${details.source || '-'}</div>
                            <div class="mb-2"><b>${this.language === 'fa' ? 'کد خطا' : 'Error Code'}:</b> ${details.code || '-'}</div>
                            <div class="mb-2"><b>${this.language === 'fa' ? 'پیام' : 'Message'}:</b> ${details.message || '-'}</div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${this.language === 'fa' ? 'بستن' : 'Close'}</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        } else {
            modal.querySelector('.modal-title').innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i> ${this.getTranslation('connectionError')}`;
            modal.querySelector('.modal-body').innerHTML = `
                <div class="mb-2"><b>${this.language === 'fa' ? 'منبع' : 'Source'}:</b> ${details.source || '-'}</div>
                <div class="mb-2"><b>${this.language === 'fa' ? 'کد خطا' : 'Error Code'}:</b> ${details.code || '-'}</div>
                <div class="mb-2"><b>${this.language === 'fa' ? 'پیام' : 'Message'}:</b> ${details.message || '-'}</div>
            `;
        }
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    updateStreamButton() {
        const btn = document.getElementById('toggleStreamBtn');
        if (!btn) return;
        if (this.isStreaming) {
            btn.innerHTML = `<i class="fas fa-stop me-2"></i> ${this.getTranslation('streamStopped')}`;
            btn.classList.add('btn-danger');
            btn.classList.remove('btn-success');
        } else {
            btn.innerHTML = `<i class="fas fa-play me-2"></i> ${this.getTranslation('streamStarted')}`;
            btn.classList.add('btn-success');
            btn.classList.remove('btn-danger');
        }
    }

    // --- تابع جدید برای ترجمه labelها و valueها در لاگ و وضعیت ---
    translateLogDetailLabels() {
        document.querySelectorAll('.log-detail-key').forEach(el => {
            let txt = el.textContent.replace(':','').trim();
            el.textContent = this.getTranslation(txt, txt) + ':';
        });
    }
    translateStatusLabels() {
        // ترجمه labelهای وضعیت (status-value و status-label)
        const statusMap = {
            'fa': {
                'Online': 'آنلاین', 'Offline': 'آفلاین', 'Connected': 'متصل', 'Disconnected': 'قطع',
                'RAM': 'رم', 'CPU': 'سی‌پی‌یو', 'Storage': 'فضای ذخیره‌سازی', 'Internet': 'اینترنت', 'Camera': 'دوربین', 'Pico': 'پیکو'
            },
            'en': {
                'آنلاین': 'Online', 'آفلاین': 'Offline', 'متصل': 'Connected', 'قطع': 'Disconnected',
                'رم': 'RAM', 'سی‌پی‌یو': 'CPU', 'فضای ذخیره‌سازی': 'Storage', 'اینترنت': 'Internet', 'دوربین': 'Camera', 'پیکو': 'Pico'
            }
        };
        document.querySelectorAll('.status-label').forEach(el => {
            const txt = el.textContent.trim();
            if (this.language === 'fa' && statusMap['fa'][txt]) el.textContent = statusMap['fa'][txt];
            if (this.language === 'en' && statusMap['en'][txt]) el.textContent = statusMap['en'][txt];
        });
        document.querySelectorAll('.status-value').forEach(el => {
            const txt = el.textContent.trim();
            if (this.language === 'fa' && statusMap['fa'][txt]) el.textContent = statusMap['fa'][txt];
            if (this.language === 'en' && statusMap['en'][txt]) el.textContent = statusMap['en'][txt];
        });
    }
    // --- تابع جدید برای ترجمه سطح لاگ (log-level-label) بعد از تغییر زبان ---
    translateLogLevelLabels() {
        document.querySelectorAll('.log-level-label').forEach(el => {
            let txt = el.textContent.trim();
            // Try to find the translation key for this label
            let key = txt;
            // Map Persian to English keys if needed
            const faToEn = {
                'دستور': 'command',
                'عکس': 'photo',
                'حذف': 'delete',
                'خطا': 'error',
                'اطلاعات': 'info',
                'هشدار': 'warning',
                'اتصال': 'connection',
                'ویدئو': 'video',
                'پشتیبان': 'backup',
                'حرکت': 'motion',
                'خروج': 'logout',
            };
            if (this.language === 'en' && faToEn[txt]) key = faToEn[txt];
            el.textContent = this.getTranslation('logLevel_' + key, key.charAt(0).toUpperCase() + key.slice(1));
        });
    }

    // Load video metadata similar to Windows file properties
    async loadVideoMetadata(videoElement, filename) {
        try {
            const response = await fetch(`/video_metadata/${filename}`);
            if (response.ok) {
                const metadata = await response.json();
                this.updateVideoMetadataDisplay(videoElement, metadata);
            }
        } catch (error) {
            console.warn('Error loading video metadata:', error);
        }
    }

    // Update video metadata display in the UI
    updateVideoMetadataDisplay(videoElement, metadata) {
        try {
            const videoItem = videoElement.closest('.video-gallery-item, .video-item');
            if (!videoItem) return;
            
            // Update metadata values
            const resolutionEl = videoItem.querySelector('.resolution-value');
            const durationEl = videoItem.querySelector('.duration-value');
            const fpsEl = videoItem.querySelector('.fps-value');
            const sizeEl = videoItem.querySelector('.video-size');
            
            if (resolutionEl && metadata.resolution) {
                resolutionEl.textContent = metadata.resolution;
            }
            
            if (durationEl && metadata.duration_formatted) {
                durationEl.textContent = metadata.duration_formatted;
            }
            
            if (fpsEl && metadata.fps) {
                fpsEl.textContent = metadata.fps;
            }
            
            if (sizeEl && metadata.file_size_formatted) {
                sizeEl.textContent = metadata.file_size_formatted;
            }
            
            // Update duration in overlay if available
            const durationOverlay = videoItem.querySelector('.video-duration');
            if (durationOverlay && metadata.duration_formatted) {
                durationOverlay.textContent = metadata.duration_formatted;
            }
            
            // Show metadata section by default
            const metadataSection = videoItem.querySelector('.video-metadata');
            if (metadataSection) {
                metadataSection.style.display = 'block';
            }
            
        } catch (error) {
            console.warn('Error updating video metadata display:', error);
        }
    }

    async checkSystemHealth() {
        try {
            const response = await fetch('/health');
            if (!response.ok) {
                throw new Error(`Health check failed: ${response.status}`);
            }
            
            const healthData = await response.json();
            
            // Update system status based on health data
            this.systemStatus.health = healthData.status;
            this.systemStatus.uptime = healthData.uptime_hours;
            this.systemStatus.esp32cam = healthData.devices.esp32cam.online ? 'online' : 'offline';
            this.systemStatus.pico = healthData.devices.pico.online ? 'online' : 'offline';
            this.systemStatus.database = healthData.database.status;
            
            // Update performance metrics
            this.systemStatus.frameCount = healthData.performance.frame_count;
            this.systemStatus.frameDropRate = healthData.performance.frame_drop_rate;
            this.systemStatus.avgLatency = healthData.performance.avg_frame_latency;
            
            // Update UI
            this.updateStatusModal();
            this.updateConnectionStatus();
            
            // Log health status
            console.log('[DEBUG] System health check:', healthData);
            
            return healthData;
            
        } catch (error) {
            console.error('[DEBUG] Health check error:', error);
            this.systemStatus.health = 'unhealthy';
            this.updateStatusModal();
            return null;
        }
    }
    
    async startHealthMonitoring() {
        // Check health every 30 seconds
        setInterval(async () => {
            await this.checkSystemHealth();
        }, 30000);
        
        // Initial health check
        await this.checkSystemHealth();
    }

}

// --- Fix footer nav button listeners for mobile ---
// This function will be called from the main initialization to avoid duplicate event listeners
function setupFooterAndButtonListeners() {
    const system = window.system;
    if (!system) return;
    
    // Setup theme/lang button listeners for desktop header
    const themeBtn = document.getElementById('themeToggle');
    const langBtn = document.getElementById('languageToggle');
    if (themeBtn) {
        themeBtn.removeEventListener('click', system.toggleTheme);
        themeBtn.addEventListener('click', (e) => { e.preventDefault(); system.toggleTheme(); });
    }
    if (langBtn) {
        langBtn.removeEventListener('click', system.toggleLanguage);
        langBtn.addEventListener('click', (e) => { e.preventDefault(); system.toggleLanguage(); });
    }
    
    // Setup theme/lang button listeners for mobile footer
    const footerThemeBtn = document.getElementById('footerThemeBtn');
    const footerLangBtn = document.getElementById('footerLangBtn');
    if (footerThemeBtn) {
        footerThemeBtn.removeEventListener('click', system.toggleTheme);
        footerThemeBtn.addEventListener('click', (e) => { e.preventDefault(); system.toggleTheme(); });
    }
    if (footerLangBtn) {
        footerLangBtn.removeEventListener('click', system.toggleLanguage);
        footerLangBtn.addEventListener('click', (e) => { e.preventDefault(); system.toggleLanguage(); });
    }
    
    // Setup footer nav SPA navigation
    const footerHomeBtn = document.getElementById('footerHomeBtn');
    const footerStatusBtn = document.getElementById('footerStatusBtn');
    const footerStoreBtn = document.getElementById('footerStoreBtn');
    if (footerHomeBtn) {
        footerHomeBtn.removeEventListener('click', showHomePage);
        footerHomeBtn.addEventListener('click', (e) => { e.preventDefault(); if (typeof showHomePage === 'function') showHomePage(); });
    }
    if (footerStatusBtn) {
        footerStatusBtn.removeEventListener('click', showStatusPage);
        footerStatusBtn.addEventListener('click', (e) => { e.preventDefault(); if (typeof showStatusPage === 'function') showStatusPage(); });
    }
    if (footerStoreBtn) {
        footerStoreBtn.removeEventListener('click', showStorePage);
        footerStoreBtn.addEventListener('click', (e) => { e.preventDefault(); if (typeof showStorePage === 'function') showStorePage(); });
    }
    
    // Responsive: show/hide header buttons on resize
    function updateHeaderButtons() {
        const themeBtn = document.getElementById('themeToggle');
        const langBtn = document.getElementById('languageToggle');
        if (window.innerWidth < 992) {
            if (themeBtn) themeBtn.style.display = 'none';
            if (langBtn) langBtn.style.display = 'none';
        } else {
            if (themeBtn) themeBtn.style.display = '';
            if (langBtn) langBtn.style.display = '';
        }
    }
    
    // Remove existing resize listener to prevent duplicates
    window.removeEventListener('resize', updateHeaderButtons);
    window.addEventListener('resize', updateHeaderButtons);
    updateHeaderButtons();
    
    // Initialize smart motion features
    if (typeof initializeSmartMotionFeatures === 'function') {
        initializeSmartMotionFeatures();
    }
    
    // Initialize smart switch state
    if (typeof initializeSmartSwitchState === 'function') {
        initializeSmartSwitchState();
    }
    
    // Update language if needed
    if (typeof system.updateLanguage === 'function') {
        system.updateLanguage(system.language || localStorage.getItem('language') || 'fa');
    }
    
    // Show home page
    if (typeof showHomePage === 'function') {
        showHomePage();
    }
    
    // Add cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (window.system && typeof window.system.cleanup === 'function') {
            window.system.cleanup();
        }
    });
    
    // Make retry function globally available
    window.retryVideo = () => {
        if (window.system && typeof window.system.retryVideo === 'function') {
            window.system.retryVideo();
        }
    };
}

// --- Add event listener for Profile button ---
function setupProfileButtonListeners() {
    const footerProfileBtn = document.getElementById('footerProfileBtn');
    if (footerProfileBtn) footerProfileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        // هیچ عملی انجام نشود (صفحه یا مودال پروفایل حذف شده است)
    });
}

// --- Smart Motion/Tracking State Management ---
function getSmartMotionState() {
    return JSON.parse(localStorage.getItem('smartMotionState') || '{"motion":false,"tracking":false}');
}
function setSmartMotionState(state) {
    localStorage.setItem('smartMotionState', JSON.stringify(state));
}
async function sendSmartFeaturesToServer(state) {
    console.log('Sending to server:', state);
    try {
        await fetch('/set_smart_features', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state)
        });
    } catch (e) { console.error('Failed to send to server', e); }
}
async function fetchSmartFeaturesFromServer() {
    try {
        const res = await fetch('/get_smart_features');
        if (res.ok) {
            const data = await res.json();
            if (data.status === 'success') {
                const state = { motion: !!data.motion, tracking: !!data.tracking };
                setSmartMotionState(state);
                updateSmartMotionToggles();
            }
        }
    } catch (e) { /* ignore */ }
}
function updateSmartMotionToggles() {
    const state = getSmartMotionState();
    // Desktop
    const motionDesktop = document.getElementById('motionDetectToggleDesktop');
    const trackingDesktop = document.getElementById('objectTrackingToggleDesktop');
    if (motionDesktop) motionDesktop.checked = !!state.motion;
    if (trackingDesktop) trackingDesktop.checked = !!state.tracking;
    // Mobile
    const motionMobile = document.getElementById('motionDetectToggleMobile');
    const trackingMobile = document.getElementById('objectTrackingToggleMobile');
    if (motionMobile) motionMobile.checked = !!state.motion;
    if (trackingMobile) trackingMobile.checked = !!state.tracking;
}
function setupSmartMotionToggleListeners() {
    // Desktop
    const motionDesktop = document.getElementById('motionDetectToggleDesktop');
    const trackingDesktop = document.getElementById('objectTrackingToggleDesktop');
    // Mobile
    const motionMobile = document.getElementById('motionDetectToggleMobile');
    const trackingMobile = document.getElementById('objectTrackingToggleMobile');
    if (motionDesktop) motionDesktop.addEventListener('change', async (e) => {
        const state = getSmartMotionState();
        state.motion = e.target.checked;
        console.log('[SMART_FEATURES] motionDesktop toggled:', state);
        setSmartMotionState(state);
        updateSmartMotionToggles();
        await sendSmartFeaturesToServer(state);
        if (window.system && typeof window.system.showNotification === 'function') {
            window.system.showNotification(
                e.target.checked ?
                    (window.system.language === 'fa' ? 'تشخیص حرکت فعال شد' : 'Motion detection enabled') :
                    (window.system.language === 'fa' ? 'تشخیص حرکت غیرفعال شد' : 'Motion detection disabled'),
                'info');
        }
    });
    if (trackingDesktop) trackingDesktop.addEventListener('change', async (e) => {
        const state = getSmartMotionState();
        state.tracking = e.target.checked;
        console.log('[SMART_FEATURES] trackingDesktop toggled:', state);
        setSmartMotionState(state);
        updateSmartMotionToggles();
        await sendSmartFeaturesToServer(state);
        if (window.system && typeof window.system.showNotification === 'function') {
            window.system.showNotification(
                e.target.checked ?
                    (window.system.language === 'fa' ? 'ردیابی هوشمند فعال شد' : 'Object tracking enabled') :
                    (window.system.language === 'fa' ? 'ردیابی هوشمند غیرفعال شد' : 'Object tracking disabled'),
                'info');
        }
    });
    if (motionMobile) motionMobile.addEventListener('change', async (e) => {
        const state = getSmartMotionState();
        state.motion = e.target.checked;
        console.log('[SMART_FEATURES] motionMobile toggled:', state);
        setSmartMotionState(state);
        updateSmartMotionToggles();
        await sendSmartFeaturesToServer(state);
        if (window.system && typeof window.system.showNotification === 'function') {
            window.system.showNotification(
                e.target.checked ?
                    (window.system.language === 'fa' ? 'تشخیص حرکت فعال شد' : 'Motion detection enabled') :
                    (window.system.language === 'fa' ? 'تشخیص حرکت غیرفعال شد' : 'Motion detection disabled'),
                'info');
        }
    });
    if (trackingMobile) trackingMobile.addEventListener('change', async (e) => {
        const state = getSmartMotionState();
        state.tracking = e.target.checked;
        console.log('[SMART_FEATURES] trackingMobile toggled:', state);
        setSmartMotionState(state);
        updateSmartMotionToggles();
        await sendSmartFeaturesToServer(state);
        if (window.system && typeof window.system.showNotification === 'function') {
            window.system.showNotification(
                e.target.checked ?
                    (window.system.language === 'fa' ? 'ردیابی هوشمند فعال شد' : 'Object tracking enabled') :
                    (window.system.language === 'fa' ? 'ردیابی هوشمند غیرفعال شد' : 'Object tracking disabled'),
                'info');
        }
    });
}
// --- Patch logs accordion and status SPA to call update/setup on render ---
const origLoadLogs = window.system && window.system.loadLogs ? window.system.loadLogs.bind(window.system) : null;
if (origLoadLogs) {
    window.system.loadLogs = async function() {
        await origLoadLogs();
        updateSmartMotionToggles();
        setupSmartMotionToggleListeners();
    };
}
// Patch showStatusPage to inject toggles at top
const origShowStatusPage = typeof showStatusPage === 'function' ? showStatusPage : null;
window.showStatusPage = function() {
    if (origShowStatusPage) origShowStatusPage();
};
// Initialize smart motion features
async function initializeSmartMotionFeatures() {
    await fetchSmartFeaturesFromServer();
    updateSmartMotionToggles();
    setupSmartMotionToggleListeners();
}

// This will be called from the main initialization
// initializeSmartMotionFeatures();
// ... existing code ...

// ... existing code ...
function saveSmartSwitchState() {
  const state = {
    motion: !!document.getElementById('motionDetectToggleDesktop')?.checked,
    tracking: !!document.getElementById('objectTrackingToggleDesktop')?.checked
  };
  localStorage.setItem('smartSwitchState', JSON.stringify(state));
}
function loadSmartSwitchState() {
  const state = JSON.parse(localStorage.getItem('smartSwitchState') || '{}');
  if (typeof state.motion !== 'undefined') {
    const el = document.getElementById('motionDetectToggleDesktop');
    if (el) el.checked = !!state.motion;
    const elMobile = document.getElementById('motionDetectToggleMobile');
    if (elMobile) elMobile.checked = !!state.motion;
  }
  if (typeof state.tracking !== 'undefined') {
    const el = document.getElementById('objectTrackingToggleDesktop');
    if (el) el.checked = !!state.tracking;
    const elMobile = document.getElementById('objectTrackingToggleMobile');
    if (elMobile) elMobile.checked = !!state.tracking;
  }
}
// Initialize smart switch state
function initializeSmartSwitchState() {
  loadSmartSwitchState();
  const motionDesktop = document.getElementById('motionDetectToggleDesktop');
  const trackingDesktop = document.getElementById('objectTrackingToggleDesktop');
  const motionMobile = document.getElementById('motionDetectToggleMobile');
  const trackingMobile = document.getElementById('objectTrackingToggleMobile');
  if (motionDesktop) motionDesktop.addEventListener('change', saveSmartSwitchState);
  if (trackingDesktop) trackingDesktop.addEventListener('change', saveSmartSwitchState);
  if (motionMobile) motionMobile.addEventListener('change', saveSmartSwitchState);
  if (trackingMobile) trackingMobile.addEventListener('change', saveSmartSwitchState);
}

// This will be called from the main DOMContentLoaded event listener
// ... existing code ...

// ... existing code ...
// اطمینان از تعریف global برای system
window.system = window.system || null;

// ... existing code ...
// تعریف تابع خالی برای جلوگیری از خطا
function updateStatusPage() {}
// ... existing code ...

// ... existing code ...
// --- SPA navigation helpers (بازگردانی شده) ---
function hideAllSpaPages() {
    document.querySelectorAll('.spa-page').forEach(page => page.style.display = 'none');
    // همچنین آکاردئون اصلی را نمایش بده
    const mainPanel = document.querySelector('.main-panel');
    if (mainPanel) mainPanel.style.display = '';
}
// تابع مشترک بازگشت به خانه از هر SPA
function goHomeFromSpa() {
    document.querySelectorAll('.spa-page').forEach(page => page.remove());
    if (window.statusPageInterval) {
        clearInterval(window.statusPageInterval);
        window.statusPageInterval = null;
    }
    const mainPanel = document.querySelector('.main-panel');
    if (mainPanel) mainPanel.style.display = '';
}
function showHomePage() {
    goHomeFromSpa();
}
let statusPageInterval = null;
function showStatusPage() {
    hideAllSpaPages();
    let oldStatusPage = document.getElementById('statusSpaPage');
    if (oldStatusPage) oldStatusPage.remove();
    let statusPage = document.createElement('div');
    statusPage.id = 'statusSpaPage';
    statusPage.className = 'spa-page status-page';
    statusPage.innerHTML = `
        <div class="status-card">
            <h2 id="spaStatusTitle"></h2>
            <ul id="spaStatusList"></ul>
            <button id="spaActiveUsersBtn" class="btn btn-outline-info mt-2"><i class="fas fa-users"></i> <span id="spaActiveUsersText"></span></button>
            <button id="spaBackBtn" class="btn btn-outline-primary mt-3"><i class="fas fa-arrow-right rtl-arrow"></i> <span id="spaBackText"></span></button>
        </div>
        <div id="spaActiveIpsModal" class="modal fade" tabindex="-1" role="dialog">
            <div class="modal-dialog modal-dialog-centered" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="fas fa-users"></i> <span id="spaActiveIpsModalTitle"></span></h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body" id="spaActiveIpsModalBody" style="max-height:350px;overflow-y:auto;padding:0.5rem 0.5rem 0.5rem 0.5rem;"></div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(statusPage);
    statusPage.style.display = 'flex';
    const mainPanel = document.querySelector('.main-panel');
    if (mainPanel) mainPanel.style.display = 'none';
    const lang = localStorage.getItem('language') || 'fa';
    // Use translations for the title and other texts
    const translations = (window.translations && window.translations[lang]) ? window.translations[lang] : {};
    document.getElementById('spaStatusTitle').textContent = translations.spaStatusTitle || (lang === 'fa' ? 'وضعیت سیستم' : 'System Status');
    document.getElementById('spaBackText').textContent = translations.spaBackText || (lang === 'fa' ? 'بازگشت' : 'Back');
    document.getElementById('spaActiveUsersText').textContent = translations.spaActiveUsers || (lang === 'fa' ? 'کاربران فعال' : 'Active Users');
    document.getElementById('spaActiveIpsModalTitle').textContent = translations.spaActiveUsers || (lang === 'fa' ? 'کاربران فعال' : 'Active Users');
    document.getElementById('spaBackBtn').onclick = goHomeFromSpa;
    document.getElementById('spaActiveUsersBtn').onclick = () => {
        const modal = new bootstrap.Modal(document.getElementById('spaActiveIpsModal'));
        modal.show();
    };
    function updateStatusPageData() {
        fetch('/get_status').then(r => r.json()).then(data => {
            if (data && data.data) {
                const statusList = document.getElementById('spaStatusList');
                statusList.innerHTML = '';
                const statusFields = [
                    { key: 'server_status', icon: 'fa-server', label: { fa: 'سرور', en: 'Server' } },
                    { key: 'camera_status', icon: 'fa-video', label: { fa: 'دوربین', en: 'Camera' } },
                    { key: 'pico_status', icon: 'fa-microchip', label: { fa: 'پیکو', en: 'Pico' } },
                    { key: 'internet', icon: 'fa-globe', label: { fa: 'اینترنت', en: 'Internet' } },
                    { key: 'storage', icon: 'fa-hdd', label: { fa: 'فضای ذخیره‌سازی', en: 'Storage' } },
                    { key: 'ram_percent', icon: 'fa-memory', label: { fa: 'درصد RAM', en: 'RAM %' } },
                    { key: 'cpu_percent', icon: 'fa-microchip', label: { fa: 'درصد CPU', en: 'CPU %' } },
                ];
                statusFields.forEach(field => {
                    let val = data.data[field.key];
                    let showVal = val;
                    let statusClass = '';
                    if (field.key.endsWith('_status') || field.key === 'internet') {
                        if (lang === 'fa') {
                            showVal = val === 'online' ? 'آنلاین' : val === 'offline' ? 'آفلاین' : val;
                        }
                        statusClass = (val === 'online' || val === 'connected') ? 'status-success' : (val === 'offline' || val === 'disconnected') ? 'status-error' : 'status-warning';
                    } else if (field.key === 'ram_percent' || field.key === 'cpu_percent') {
                        if (val !== undefined && val !== null) {
                            showVal = val + '%';
                            statusClass = val < 70 ? 'status-success' : val < 90 ? 'status-warning' : 'status-error';
                        } else {
                            showVal = lang === 'fa' ? 'نامشخص' : 'Unknown';
                            statusClass = 'status-warning';
                        }
                    } else if (field.key === 'storage') {
                        if (val && typeof val === 'string' && val.match(/\d+\.\d+%/)) {
                            showVal = val;
                            statusClass = parseFloat(val) > 20 ? 'status-success' : 'status-warning';
                        } else {
                            showVal = lang === 'fa' ? 'نامشخص' : 'Unknown';
                            statusClass = 'status-warning';
                        }
                    }
                    statusList.innerHTML += `
                        <li><i class="fas ${field.icon}"></i> ${field.label[lang]}: <span class="status-value ${statusClass}">${showVal ?? (lang === 'fa' ? 'نامشخص' : 'Unknown')}</span></li>
                    `;
                });
                const ips = data.data.active_ips || [];
                const modalBody = document.getElementById('spaActiveIpsModalBody');
                if (ips.length) {
                    let html = '<div style="display:flex;flex-direction:column;gap:10px;">';
                    ips.forEach(ip => {
                        html += `<div style="border:1px solid #eee;border-radius:10px;padding:8px 10px 8px 10px;margin-bottom:0;box-shadow:0 2px 8px rgba(0,0,0,0.04);font-size:0.98em;word-break:break-all;overflow-wrap:anywhere;">
                            <div style="display:flex;align-items:center;gap:6px;"><i class='fas fa-network-wired'></i> <b>${lang === 'fa' ? 'آی‌پی' : 'IP'}:</b> <span>${ip.ip}</span></div>
                            <div style="display:flex;align-items:center;gap:6px;"><i class='fas fa-clock'></i> <b>${lang === 'fa' ? 'زمان اتصال' : 'Connect Time'}:</b> <span>${new Date(ip.connect_time).toLocaleString(lang === 'fa' ? 'fa-IR' : 'en-US')}</span></div>
                            <div style="display:flex;align-items:center;gap:6px;"><i class='fas fa-history'></i> <b>${lang === 'fa' ? 'آخرین فعالیت' : 'Last Activity'}:</b> <span>${new Date(ip.last_activity).toLocaleString(lang === 'fa' ? 'fa-IR' : 'en-US')}</span></div>
                            <div style="display:flex;align-items:center;gap:6px;"><i class='fas fa-desktop'></i> <b>User-Agent:</b> <span style="font-size:0.93em;max-width:180px;display:inline-block;white-space:nowrap;overflow-x:auto;">${ip.user_agent || '-'}</span></div>
                        </div>`;
                    });
                    html += '</div>';
                    modalBody.innerHTML = html;
                } else {
                    modalBody.innerHTML = `<span>${lang === 'fa' ? 'هیچ کاربر فعالی وجود ندارد.' : 'No active users.'}</span>`;
                }
            }
        });
    }
    updateStatusPageData();
    window.statusPageInterval = setInterval(updateStatusPageData, 30000); // Reduced from 5 to 30 seconds
}

// ... existing code ...
// Typewriter header
function runHeaderTypewriter() {
    const el = document.getElementById('headerTypewriter');
    if (!el) return;
    const lang = document.documentElement.lang || (document.body.classList.contains('lang-en') ? 'en' : 'fa');
    // Use translations if available, else fallback
    let messages = (window.translations && window.translations[lang] && window.translations[lang]['typewriterHeader']) || null;
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
        messages = lang === 'fa' ? [
            'امنیت هوشمند، آینده‌ای مطمئن 🛡️',
            'نظارت زنده، آرامش خاطر 👁️',
            'هوش مصنوعی در خدمت امنیت شما 🤖',
            'حفاظت ۲۴/۷ با فناوری نوین 🔒',
            'کنترل سریع، واکنش هوشمند ⚡',
            'دسترسی آسان از هر نقطه 🌐',
            'ثبت لحظات مهم امنیتی 📸',
            'امنیت خانه و محل کار شما 🛡️',
            'اتصال پایدار و بی‌وقفه 🛰️'
        ] : [
            'Smart Security, Confident Future 🛡️',
            'Live Monitoring, Peace of Mind 👁️',
            'AI-Powered Protection 🤖',
            '24/7 Safety with Innovation 🔒',
            'Fast Control, Smart Response ⚡',
            'Easy Access, Anywhere 🌐',
            'Capture Every Security Moment 📸',
            'Protecting Home & Business 🛡️',
            'Reliable, Uninterrupted Connection 🛰️'
        ];
    }
    let msgIdx = 0;
    let i = 0;
    let typing = true;
    let cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    cursor.textContent = '|';
    cursor.style.direction = (lang === 'fa') ? 'rtl' : 'ltr';
    el.textContent = '';
    el.dir = (lang === 'fa') ? 'rtl' : 'ltr';
    el.appendChild(cursor);
    if (!el.firstChild || el.firstChild.nodeType !== 3) {
        el.insertBefore(document.createTextNode(''), cursor);
    }
    if (window.headerTypewriterTimeout) {
        clearTimeout(window.headerTypewriterTimeout);
        window.headerTypewriterTimeout = null;
    }
    function type() {
        const text = messages[msgIdx];
        if (typing) {
            if (i <= text.length) {
                el.childNodes[0].textContent = text.slice(0, i);
                i++;
                window.headerTypewriterTimeout = setTimeout(type, lang === 'fa' ? 38 : 28);
            } else {
                typing = false;
                window.headerTypewriterTimeout = setTimeout(type, 1200);
            }
        } else {
            if (i > 0) {
                el.childNodes[0].textContent = text.slice(0, i);
                i--;
                window.headerTypewriterTimeout = setTimeout(type, 18);
            } else {
                el.childNodes[0].textContent = '';
                typing = true;
                msgIdx = (msgIdx + 1) % messages.length;
                window.headerTypewriterTimeout = setTimeout(type, 500);
            }
        }
    }
    if (window.headerTypewriterInterval) clearInterval(window.headerTypewriterInterval);
    window.headerTypewriterInterval = setInterval(() => {
        cursor.style.opacity = cursor.style.opacity === '0' ? '1' : '0';
    }, 480);
    type();
}
function runFooterTypewriter() {
    const el = document.getElementById('footerTypewriter');
    if (!el) return;
    const lang = document.documentElement.lang || (document.body.classList.contains('lang-en') ? 'en' : 'fa');
    let messages = (window.translations && window.translations[lang] && window.translations[lang]['typewriterFooter']) || null;
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
        messages = lang === 'fa'
            ? [
                'امنیت خانه و محل کار با ما! 🏠🔒',
                'پشتیبانی حرفه‌ای و سریع 🚀',
                'دسترسی آسان از هرجا 🌍',
                'گزارش‌های تصویری و آماری 📈',
                'تجربه امنیت هوشمند با هوش مصنوعی 🤖',
                'ارتباط با ما همیشه باز است 📞',
                'به‌روزرسانی خودکار و رایگان 🔄'
            ]
            : [
                'Secure your home & business! 🏠🔒',
                'Fast & professional support 🚀',
                'Easy access from anywhere 🌍',
                'Visual & statistical reports 📈',
                'Smart security powered by AI 🤖',
                'We are always here for you 📞',
                'Free automatic updates 🔄'
            ];
    }
    let msgIdx = 0;
    let i = 0;
    let typing = true;
    let cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    cursor.textContent = '|';
    cursor.style.direction = (lang === 'fa') ? 'rtl' : 'ltr';
    el.textContent = '';
    el.dir = (lang === 'fa') ? 'rtl' : 'ltr';
    el.appendChild(cursor);
    if (!el.firstChild || el.firstChild.nodeType !== 3) {
        el.insertBefore(document.createTextNode(''), cursor);
    }
    if (window.footerTypewriterTimeout) {
        clearTimeout(window.footerTypewriterTimeout);
        window.footerTypewriterTimeout = null;
    }
    function type() {
        const text = messages[msgIdx];
        if (typing) {
            if (i <= text.length) {
                el.childNodes[0].textContent = text.slice(0, i);
                i++;
                window.footerTypewriterTimeout = setTimeout(type, lang === 'fa' ? 32 : 22);
            } else {
                typing = false;
                window.footerTypewriterTimeout = setTimeout(type, 1200);
            }
        } else {
            if (i > 0) {
                el.childNodes[0].textContent = text.slice(0, i);
                i--;
                window.footerTypewriterTimeout = setTimeout(type, 14);
            } else {
                el.childNodes[0].textContent = '';
                typing = true;
                msgIdx = (msgIdx + 1) % messages.length;
                window.footerTypewriterTimeout = setTimeout(type, 500);
            }
        }
    }
    if (window.footerTypewriterInterval) clearInterval(window.footerTypewriterInterval);
    window.footerTypewriterInterval = setInterval(() => {
        cursor.style.opacity = cursor.style.opacity === '0' ? '1' : '0';
    }, 480);
    type();
}
// ... existing code ...

// ... existing code ...
function setupHeaderHideOnScroll() {
    const header = document.querySelector('.main-header');
    if (!header) return;
    function onScroll() {
        if (window.innerWidth < 992) {
            header.classList.remove('hidden');
            return;
        }
        if (window.scrollY === 0) {
            header.classList.remove('hidden');
        } else {
            header.classList.add('hidden');
        }
    }
    window.addEventListener('scroll', onScroll);
    window.addEventListener('resize', () => {
        if (window.innerWidth < 992) header.classList.remove('hidden');
        else onScroll();
    });
    onScroll(); // اجرا در ابتدا
}
// Initialize typewriter and header functionality
function setupTypewriterAndHeader() {
    runHeaderTypewriter();
    runFooterTypewriter();
    setupHeaderHideOnScroll();
}

// ... existing code ...
// --- Force scroll to top on every page load/reload, even after SPA or late scripts ---
// Disable browser scroll restoration
if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
}

// Single scroll to top function
function scrollToTop() {
    window.scrollTo(0, 0);
    document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;
}

// Apply scroll to top on page load
function setupScrollToTop() {
    setTimeout(scrollToTop, 0);
}

window.onload = function() {
    setTimeout(scrollToTop, 0);
};

// ... existing code ...
// --- Status Modal HTML injection (if not present) ---
function ensureStatusModal() {
    if (document.getElementById('statusModal')) return;
    const t = window.system ? window.system.getTranslation.bind(window.system) : (k, f) => f || k;
    const isDark = document.body.classList.contains('dark-mode');
    const modal = document.createElement('div');
    modal.id = 'statusModal';
    modal.className = 'modal fade';
    modal.tabIndex = -1;
    modal.innerHTML = `
        <div class="modal-dialog status-modal-dialog" style="max-width:430px;width:97vw;">
            <div class="modal-content status-modal-content ${isDark ? 'dark' : 'light'}">
                <div class="modal-header status-modal-header ${isDark ? 'dark' : 'light'}">
                    <h5 class="modal-title status-modal-title" id="statusModalTitle" data-key="spaStatusTitle"><i class="fas fa-info-circle me-2"></i> ${t('spaStatusTitle')}</h5>
                    <button type="button" class="status-modal-x-btn" data-bs-dismiss="modal" aria-label="Close" title="${t('close')}">
                        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <circle cx="14" cy="14" r="13" fill="${isDark ? '#232b3b' : '#fff'}" stroke="${isDark ? '#4fc3f7' : '#1976d2'}" stroke-width="2"/>
                            <path d="M9 9L19 19M19 9L9 19" stroke="${isDark ? '#4fc3f7' : '#1976d2'}" stroke-width="2.2" stroke-linecap="round"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body status-modal-body ${isDark ? 'dark' : 'light'}">
                    <ul id="statusModalList" class="status-modal-list" style="list-style:none;padding:0;margin:0 0 10px 0;"></ul>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    // استایل جذاب و مدرن برای مودال وضعیت و دکمه X و لیست
    const style = document.createElement('style');
    style.innerHTML = `
    .status-modal-dialog {
        max-width:430px !important;
        width:97vw !important;
        margin: 2.5rem auto !important;
    }
    .status-modal-content {
        border-radius: 1.4rem;
        box-shadow: 0 8px 32px 0 rgba(25, 118, 210, 0.16), 0 2px 8px 0 rgba(0,0,0,0.10);
        padding: 0.5rem 0.5rem 0.5rem 0.5rem;
        background: linear-gradient(135deg, ${isDark ? '#232b3b' : '#fafdff'} 0%, ${isDark ? '#26334d' : '#e3f0ff'} 100%);
        color: ${isDark ? '#e3f0ff' : '#232b3b'};
        border: none;
        transition: background 0.2s, color 0.2s;
    }
    .status-modal-header {
        border-bottom: none;
        padding: 1.2rem 1.3rem 0.7rem 1.3rem;
        background: transparent;
        display: flex; align-items: center; justify-content: space-between;
        color: ${isDark ? '#4fc3f7' : '#1976d2'};
    }
    .status-modal-title {
        font-size: 1.25rem;
        font-weight: 800;
        letter-spacing: 0.01em;
        color: ${isDark ? '#4fc3f7' : '#1976d2'};
        display: flex; align-items: center;
    }
    .status-modal-x-btn {
        background: none;
        border: none;
        outline: none;
        cursor: pointer;
        padding: 0.1rem;
        border-radius: 50%;
        transition: box-shadow 0.18s, background 0.18s, transform 0.18s;
        box-shadow: 0 2px 8px rgba(25,118,210,0.10);
        display: flex; align-items: center; justify-content: center;
    }
    .status-modal-x-btn:hover, .status-modal-x-btn:focus {
        background: ${isDark ? '#4fc3f7' : '#e3f0ff'};
        box-shadow: 0 4px 16px rgba(25,118,210,0.22);
        transform: scale(1.13) rotate(-8deg);
    }
    .status-modal-x-btn svg { display: block; }
    .status-modal-body {
        padding: 0.9rem 1.3rem 1.3rem 1.3rem;
        font-size: 1.13rem;
        color: ${isDark ? '#e3f0ff' : '#232b3b'};
    }
    .status-modal-list li {
        margin-bottom: 0.85em;
        font-size: 1.13em;
        font-weight: 600;
        border-radius: 0.7em;
        padding: 0.45em 0.7em 0.45em 0.7em;
        display: flex; align-items: center; gap: 0.7em;
        background: ${isDark ? 'rgba(255,255,255,0.03)' : 'rgba(25,118,210,0.04)'};
        box-shadow: 0 1.5px 6px 0 rgba(25,118,210,0.04);
        transition: background 0.18s, box-shadow 0.18s;
    }
    .status-modal-list li:hover {
        background: ${isDark ? 'rgba(79,195,247,0.10)' : 'rgba(25,118,210,0.10)'};
        box-shadow: 0 3px 12px 0 rgba(25,118,210,0.10);
    }
    .status-modal-list .status-label-icon {
        font-size: 1.18em;
        margin-left: 0.18em;
        margin-right: 0.18em;
        vertical-align: middle;
    }
    .status-value {
        font-weight: bold;
        margin-right: 0.3em;
        font-size: 1.09em;
        letter-spacing: 0.01em;
    }
    .status-value.online { color: #43b66e; }
    .status-value.offline { color: #e53935; }
    .status-value.info { color: #1976d2; }
    .status-value.dark.online { color: #4fc3f7; }
    .status-value.dark.offline { color: #ff8a80; }
    .status-value.dark.info { color: #90caf9; }
    @media (max-width: 600px) {
        .status-modal-dialog {
            max-width: 99vw !important;
            margin: 1.2rem auto !important;
        }
        .status-modal-content {
            border-radius: 0.8rem;
            padding: 0.2rem 0.2rem 0.5rem 0.2rem;
        }
        .status-modal-header, .status-modal-body {
            padding-left: 0.7rem; padding-right: 0.7rem;
        }
    }
        `;
    document.head.appendChild(style);
}

// --- Show Status Modal ---
async function showStatusModal() {
    ensureStatusModal();
    const lang = localStorage.getItem('language') || 'fa';
    const modalEl = document.getElementById('statusModal');
    const bsModal = new bootstrap.Modal(modalEl);
    // Clean up overlays on close
    modalEl.removeEventListener('hidden.bs.modal', window._statusModalCleanup);
    window._statusModalCleanup = function() {
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    };
    modalEl.addEventListener('hidden.bs.modal', window._statusModalCleanup);
    // Fetch and fill status
    try {
        const res = await fetch('/get_status');
        let d = {};
        if (res.ok) {
            const statusData = await res.json();
            if (statusData.status === 'success' && statusData.data) d = statusData.data;
        }
        const statusList = document.getElementById('statusModalList');
        statusList.innerHTML = '';
        const statusFields = [
            { key: 'server_status', icon: 'fa-server', label: { fa: 'سرور', en: 'Server' } },
            { key: 'camera_status', icon: 'fa-video', label: { fa: 'دوربین', en: 'Camera' } },
            { key: 'pico_status', icon: 'fa-microchip', label: { fa: 'پیکو', en: 'Pico' } },
            { key: 'internet', icon: 'fa-globe', label: { fa: 'اینترنت', en: 'Internet' } },
            { key: 'storage', icon: 'fa-hdd', label: { fa: 'فضای ذخیره‌سازی', en: 'Storage' } },
            { key: 'ram_percent', icon: 'fa-memory', label: { fa: 'درصد RAM', en: 'RAM %' } },
            { key: 'cpu_percent', icon: 'fa-microchip', label: { fa: 'درصد CPU', en: 'CPU %' } },
        ];
        statusFields.forEach(field => {
            let val = d[field.key];
            let showVal = val;
            let statusClass = '';
            if (field.key.endsWith('_status') || field.key === 'internet') {
                if (lang === 'fa') {
                    showVal = val === 'online' ? 'آنلاین' : val === 'offline' ? 'آفلاین' : val;
                } else {
                    showVal = val === 'online' ? 'Online' : val === 'offline' ? 'Offline' : val;
                }
                statusClass = (val === 'online' || val === 'connected') ? 'status-success' : (val === 'offline' || val === 'disconnected') ? 'status-error' : 'status-warning';
            } else if (field.key === 'ram_percent' || field.key === 'cpu_percent') {
                if (val !== undefined && val !== null) {
                    showVal = val + '%';
                    statusClass = val < 70 ? 'status-success' : val < 90 ? 'status-warning' : 'status-error';
                } else {
                    showVal = lang === 'fa' ? 'نامشخص' : 'Unknown';
                    statusClass = 'status-warning';
                }
            } else if (field.key === 'storage') {
                if (val && typeof val === 'string' && val.match(/\d+\.\d+%/)) {
                    showVal = val;
                    statusClass = parseFloat(val) > 20 ? 'status-success' : 'status-warning';
                } else {
                    showVal = lang === 'fa' ? 'نامشخص' : 'Unknown';
                    statusClass = 'status-warning';
                }
            }
            statusList.innerHTML += `
                <li style="margin-bottom:7px;"><i class="fas ${field.icon}"></i> ${field.label[lang]}: <span class="status-value ${statusClass}">${showVal ?? (lang === 'fa' ? 'نامشخص' : 'Unknown')}</span></li>
            `;
        });
        // دکمه کاربران فعال حذف شد
    } catch {}
    bsModal.show();
}
// ... existing code ...

// ... existing code ...
// Remove or disable SPA status page logic (showStatusPage)
function showStatusPage() {
    // Disabled: Only modal is used now
    showStatusModal();
}
// ... existing code ...

// ... existing code ...
// Utility to set button text with icon, no emoji
function setLogsAccordionButtonTexts(language) {
    const showAllLogsBtn = document.getElementById('showAllLogsBtn');
    if (showAllLogsBtn) {
        showAllLogsBtn.innerHTML = `<i class='fas fa-list'></i> ` + (language === 'fa' ? 'نمایش همه گزارش‌ها' : 'Show all logs');
    }
    const refreshLogsBtn = document.getElementById('refreshLogsBtn');
    if (refreshLogsBtn) {
        refreshLogsBtn.innerHTML = `<i class='fas fa-sync-alt'></i> ` + (language === 'fa' ? 'به‌روزرسانی گزارش‌ها' : 'Refresh logs');
    }
}

// Patch updateLanguage to also update button texts
const origUpdateLanguage = SmartCameraSystem.prototype.updateLanguage;
SmartCameraSystem.prototype.updateLanguage = async function(lang) {
    await origUpdateLanguage.call(this, lang);
    setLogsAccordionButtonTexts(lang);
};

// Setup logs accordion button texts
function setupLogsAccordionButtonTexts() {
    setLogsAccordionButtonTexts(localStorage.getItem('language') || 'fa');
}
// ... existing code ...

// ... existing code ...
// Add debounce utility at the top or in the class
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}
// ... existing code ...
// In SmartCameraSystem class, replace direct servo command sending with debounced version
// Find the method that sends servo commands (e.g., sendServoCommand or similar)
// Replace its usage in the UI event handlers with a debounced version:

// Example:
this.debouncedSendServoCommand = debounce((servo1, servo2) => {
    this.sendServoCommand(servo1, servo2);
}, 350);


// Patch reconnect logic
let reconnectTimeout = null;
SmartCameraSystem.prototype.scheduleReconnect = function() {
    if (reconnectTimeout) return;
    reconnectTimeout = setTimeout(() => {
        reconnectTimeout = null;
        this.setupWebSocket().catch(err => console.error('[DEBUG] Reconnection error:', err));
    }, 3000); // 3 seconds delay between reconnects
};
// ... existing code ...

// This functionality is now handled in the main DOMContentLoaded event listener above

function updateSpaPagesLanguage(lang) {
    if (window.translations && window.translations[lang]) {
        document.querySelectorAll('.spa-page [data-key]').forEach(el => {
            const key = el.getAttribute('data-key');
            if (window.translations[lang][key]) {
                el.textContent = window.translations[lang][key];
            }
        });
        document.querySelectorAll('.spa-page [data-key-title]').forEach(el => {
            const key = el.getAttribute('data-key-title');
            if (window.translations[lang][key]) {
                el.setAttribute('title', window.translations[lang][key]);
            }
        });
        document.querySelectorAll('.spa-page [data-key-placeholder]').forEach(el => {
            const key = el.getAttribute('data-key-placeholder');
            if (window.translations[lang][key]) {
                el.setAttribute('placeholder', window.translations[lang][key]);
            }
        });
        document.querySelectorAll('.spa-page [data-key-alt]').forEach(el => {
            const key = el.getAttribute('data-key-alt');
            if (window.translations[lang][key]) {
                el.setAttribute('alt', window.translations[lang][key]);
            }
        });
    }
}

// Global retry function for video modal
function retryVideo() {
    if (window.system && typeof window.system.retryVideo === 'function') {
        window.system.retryVideo();
    }
}



// Initialize system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Prevent multiple initializations
    if (window.system && window.system.isInitialized) {
        console.log('⚠️ System already initialized, skipping duplicate initialization');
        return;
    }
    
    try {
        // Create and initialize the smart camera system
        window.system = new SmartCameraSystem();
        window.system.init();
        window.system.isInitialized = true; // Mark as initialized
        
        // Start health monitoring
        window.system.startHealthMonitoring();
        
        console.log('✅ Smart Camera System initialized successfully');
        
        // Setup all additional functionality after system initialization
        if (typeof setupFooterAndButtonListeners === 'function') {
            setupFooterAndButtonListeners();
        }
        
        if (typeof setupProfileButtonListeners === 'function') {
            setupProfileButtonListeners();
        }
        
        if (typeof setupTypewriterAndHeader === 'function') {
            setupTypewriterAndHeader();
        }
        
        if (typeof setupScrollToTop === 'function') {
            setupScrollToTop();
        }
        
        if (typeof setupLogsAccordionButtonTexts === 'function') {
            setupLogsAccordionButtonTexts();
        }
        
        if (typeof initializeSmartMotionFeatures === 'function') {
            initializeSmartMotionFeatures();
        }
        
        if (typeof initializeSmartSwitchState === 'function') {
            initializeSmartSwitchState();
        }
        
    } catch (error) {
        console.error('❌ Error initializing Smart Camera System:', error);
    }
});

