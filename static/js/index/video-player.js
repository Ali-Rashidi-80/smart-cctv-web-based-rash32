/**
 * Modern Video Player System
 * Professional video player with custom controls and enhanced functionality
 */
class ModernVideoPlayer {
    constructor() {
        this.video = null;
        this.controls = null;
        this.progressBar = null;
        this.progressFill = null;
        this.progressHandle = null;
        this.currentTime = null;
        this.duration = null;
        this.playPauseBtn = null;
        this.volumeBtn = null;
        this.fullscreenBtn = null;
        this.loadingOverlay = null;
        this.errorOverlay = null;
        this.retryBtn = null;
        
        this.isPlaying = false;
        this.isMuted = false;
        this.currentVolume = 0.5;
        this.isFullscreen = false;
        this.isDragging = false;
        this.updateInterval = null;
        
        this.init();
    }
    
    init() {
        // Prevent multiple initializations
        if (this._isInitialized) {
            console.log('⚠️ Video player already initialized, skipping duplicate initialization');
            return;
        }
        
        this.initializeElements();
        this.setupEventListeners();
        this.setupVideoEventListeners();
        this.setupControlEventListeners();
        this.setupProgressBar();
        this.setupVolumeControl();
        this.setupFullscreenControl();
        this.setupModalCleanup();
        
        this._isInitialized = true; // Mark as initialized
    }
    
    initializeElements() {
        this.video = document.getElementById('mainVideoPlayer');
        this.controls = document.querySelector('.custom-video-controls');
        this.progressBar = document.querySelector('.progress-bar');
        this.progressFill = document.querySelector('.progress-fill');
        this.progressHandle = document.querySelector('.progress-handle');
        this.currentTime = document.querySelector('.current-time');
        this.duration = document.querySelector('.duration');
        this.playPauseBtn = document.getElementById('playPauseBtn');
        this.volumeBtn = document.getElementById('volumeBtn');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.loadingOverlay = document.getElementById('videoLoadingOverlay');
        this.errorOverlay = document.getElementById('videoErrorOverlay');
        this.retryBtn = document.getElementById('retryVideoBtn');
        
        // Debug: Log all found elements
        this.debugElements();
        
        if (!this.video) {
            console.error('Video player elements not found');
            return;
        }
    }
    
    setupEventListeners() {
        // Video event listeners
        this.video.addEventListener('loadstart', () => this.onLoadStart());
        this.video.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.addEventListener('canplay', () => this.onCanPlay());
        this.video.addEventListener('canplaythrough', () => this.onCanPlayThrough());
        this.video.addEventListener('error', (e) => this.onError(e));
        this.video.addEventListener('abort', () => this.onAbort());
        this.video.addEventListener('stalled', () => this.onStalled());
        this.video.addEventListener('suspend', () => this.onSuspend());
        this.video.addEventListener('waiting', () => this.onWaiting());
        
        // Control event listeners
        this.playPauseBtn?.addEventListener('click', () => this.togglePlayPause());
        this.volumeBtn?.addEventListener('click', () => this.toggleMute());
        this.fullscreenBtn?.addEventListener('click', () => this.toggleFullscreen());
        this.retryBtn?.addEventListener('click', () => this.retryVideo());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        
        // Mouse events for progress bar
        this.progressBar?.addEventListener('mousedown', (e) => this.startSeeking(e));
        document.addEventListener('mousemove', (e) => this.seek(e));
        document.addEventListener('mouseup', () => this.stopSeeking());
        
        // Touch events for mobile
        this.progressBar?.addEventListener('touchstart', (e) => this.startSeeking(e));
        document.addEventListener('touchmove', (e) => this.seek(e));
        document.addEventListener('touchend', () => this.stopSeeking());
    }
    
    setupVideoEventListeners() {
        // Time update
        this.video.addEventListener('timeupdate', () => {
            this.updateProgress();
            this.updateTimeDisplay();
        });
        
        // Duration change
        this.video.addEventListener('durationchange', () => {
            this.updateDuration();
        });
        
        // Play/Pause events
        this.video.addEventListener('play', () => {
            this.isPlaying = true;
            this.updatePlayPauseButton();
        });
        
        this.video.addEventListener('pause', () => {
            this.isPlaying = false;
            this.updatePlayPauseButton();
        });
        
        // Volume change
        this.video.addEventListener('volumechange', () => {
            this.currentVolume = this.video.volume;
            this.updateVolumeButton();
        });
        
        // Fullscreen change
        this.video.addEventListener('fullscreenchange', () => {
            this.isFullscreen = !!document.fullscreenElement;
            this.updateFullscreenButton();
        });
    }
    
    setupControlEventListeners() {
        // Volume slider
        const volumeRange = this.volumeSlider?.querySelector('.volume-range');
        if (volumeRange) {
            volumeRange.addEventListener('input', (e) => {
                const volume = e.target.value / 100;
                this.setVolume(volume);
            });
        }
        
        // Progress bar click
        this.progressBar?.addEventListener('click', (e) => {
            if (!this.isDragging) {
                this.seekToPosition(e);
            }
        });
    }
    
    setupProgressBar() {
        if (!this.progressBar || !this.progressFill || !this.progressHandle) return;
        
        // Progress bar interaction
        this.progressBar.addEventListener('mousedown', (e) => this.startSeeking(e));
        this.progressBar.addEventListener('touchstart', (e) => this.startSeeking(e));
    }
    
    setupVolumeControl() {
        // Volume slider is removed from modal, so we'll use a simple click to toggle mute
        if (this.volumeBtn) {
            // Set initial volume
            this.setVolume(this.currentVolume);
        }
    }
    
    setupFullscreenControl() {
        // Check fullscreen support
        if (!document.fullscreenEnabled && 
            !document.webkitFullscreenEnabled && 
            !document.mozFullScreenEnabled && 
            !document.msFullscreenEnabled) {
            this.fullscreenBtn?.setAttribute('disabled', 'true');
        }
    }
    
    // Video Event Handlers
    onLoadStart() {
        console.log('Video loading started');
        this.showLoading();
        this.hideError();
    }
    
    onLoadedMetadata() {
        console.log('Video metadata loaded');
        this.updateDuration();
        this.hideLoading();
        
        // Ensure video is properly displayed
        if (this.video) {
            this.video.style.display = 'block';
        }
    }
    
    onCanPlay() {
        console.log('Video can play');
        this.hideLoading();
        this.hideError();
        
        // Ensure video is visible
        if (this.video) {
            this.video.style.display = 'block';
        }
    }
    
    onCanPlayThrough() {
        console.log('Video can play through');
        this.hideLoading();
        this.hideError();
        this.startUpdateInterval();
        
        // Ensure video is visible and ready
        if (this.video) {
            this.video.style.display = 'block';
        }
    }
    
    onError(e) {
        console.error('Video error:', e);
        this.showError();
        this.hideLoading();
        this.stopUpdateInterval();
        
        // Hide video on error
        if (this.video) {
            this.video.style.display = 'none';
        }
    }
    
    onAbort() {
        console.warn('Video loading aborted');
        this.hideLoading();
    }
    
    onStalled() {
        console.warn('Video stalled');
        this.showLoading();
    }
    
    onSuspend() {
        console.log('Video loading suspended');
    }
    
    onWaiting() {
        console.log('Video waiting for data');
        this.showLoading();
    }
    
    // Control Methods
    togglePlayPause() {
        if (this.video.paused) {
            this.play();
        } else {
            this.pause();
        }
    }
    
    play() {
        this.video.play().catch(e => {
            console.error('Error playing video:', e);
            this.showError();
        });
    }
    
    pause() {
        this.video.pause();
    }
    
    toggleMute() {
        this.video.muted = !this.video.muted;
        this.isMuted = this.video.muted;
        this.updateVolumeButton();
    }
    
    setVolume(volume) {
        this.video.volume = Math.max(0, Math.min(1, volume));
        this.currentVolume = this.video.volume;
        this.updateVolumeButton();
        
        // No volume slider to update since it's removed
    }
    
    toggleFullscreen() {
        if (this.isFullscreen) {
            this.exitFullscreen();
        } else {
            this.enterFullscreen();
        }
    }
    
    enterFullscreen() {
        if (this.video.requestFullscreen) {
            this.video.requestFullscreen();
        } else if (this.video.webkitRequestFullscreen) {
            this.video.webkitRequestFullscreen();
        } else if (this.video.mozRequestFullScreen) {
            this.video.mozRequestFullScreen();
        } else if (this.video.msRequestFullscreen) {
            this.video.msRequestFullscreen();
        }
    }
    
    exitFullscreen() {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
    
    // Progress Bar Methods
    startSeeking(e) {
        this.isDragging = true;
        this.seek(e);
    }
    
    seek(e) {
        if (!this.isDragging) return;
        
        const rect = this.progressBar.getBoundingClientRect();
        const clientX = e.clientX || (e.touches && e.touches[0].clientX);
        const clickX = clientX - rect.left;
        const percentage = clickX / rect.width;
        
        this.seekToPercentage(percentage);
    }
    
    stopSeeking() {
        this.isDragging = false;
    }
    
    seekToPosition(e) {
        const rect = this.progressBar.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const percentage = clickX / rect.width;
        
        this.seekToPercentage(percentage);
    }
    
    seekToPercentage(percentage) {
        if (this.video.duration) {
            const newTime = percentage * this.video.duration;
            this.video.currentTime = newTime;
        }
    }
    
    // Update Methods
    updateProgress() {
        if (!this.video.duration) return;
        
        const percentage = (this.video.currentTime / this.video.duration) * 100;
        this.progressFill.style.width = percentage + '%';
        this.progressHandle.style.left = percentage + '%';
    }
    
    updateTimeDisplay() {
        if (this.currentTime) {
            this.currentTime.textContent = this.formatTime(this.video.currentTime);
        }
    }
    
    updateDuration() {
        if (this.duration) {
            this.duration.textContent = this.formatTime(this.video.duration);
        }
    }
    
    updatePlayPauseButton() {
        if (this.playPauseBtn) {
            const icon = this.playPauseBtn.querySelector('i');
            if (icon) {
                icon.className = this.isPlaying ? 'fas fa-pause' : 'fas fa-play';
            }
        }
    }
    
    updateVolumeButton() {
        if (this.volumeBtn) {
            const icon = this.volumeBtn.querySelector('i');
            if (icon) {
                if (this.video.muted || this.video.volume === 0) {
                    icon.className = 'fas fa-volume-mute';
                } else if (this.video.volume < 0.5) {
                    icon.className = 'fas fa-volume-down';
                } else {
                    icon.className = 'fas fa-volume-up';
                }
            }
        }
    }
    
    updateFullscreenButton() {
        if (this.fullscreenBtn) {
            const icon = this.fullscreenBtn.querySelector('i');
            if (icon) {
                icon.className = this.isFullscreen ? 'fas fa-compress' : 'fas fa-expand';
            }
        }
    }
    
    // Utility Methods
    formatTime(seconds) {
        if (isNaN(seconds)) return '00:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    showLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.style.display = 'flex';
        }
    }
    
    hideLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.style.display = 'none';
        }
    }
    
    showError() {
        if (this.errorOverlay) {
            this.errorOverlay.style.display = 'flex';
        }
    }
    
    hideError() {
        if (this.errorOverlay) {
            this.errorOverlay.style.display = 'none';
        }
    }
    
    retryVideo() {
        this.hideError();
        this.showLoading();
        this.video.load();
    }
    
    // Keyboard Shortcuts
    handleKeyboard(e) {
        if (!this.video) return;
        
        switch (e.key.toLowerCase()) {
            case ' ':
            case 'k':
                e.preventDefault();
                this.togglePlayPause();
                break;
            case 'm':
                e.preventDefault();
                this.toggleMute();
                break;
            case 'f':
                e.preventDefault();
                this.toggleFullscreen();
                break;
            case 'arrowleft':
                e.preventDefault();
                this.video.currentTime = Math.max(0, this.video.currentTime - 10);
                break;
            case 'arrowright':
                e.preventDefault();
                this.video.currentTime = Math.min(this.video.duration, this.video.currentTime + 10);
                break;
            case 'arrowup':
                e.preventDefault();
                this.setVolume(Math.min(1, this.currentVolume + 0.1));
                break;
            case 'arrowdown':
                e.preventDefault();
                this.setVolume(Math.max(0, this.currentVolume - 0.1));
                break;
        }
    }
    
    // Interval Management
    startUpdateInterval() {
        if (this.updateInterval) return;
        
        this.updateInterval = setInterval(() => {
            this.updateProgress();
            this.updateTimeDisplay();
        }, 100);
    }
    
    stopUpdateInterval() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    // Public API Methods
    loadVideo(src, title = '') {
        if (!this.video) return;
        
        console.log('Loading video:', src);
        
        this.video.src = src;
        this.video.load();
        
        // Update title
        const titleElement = document.getElementById('videoPlayerTitle');
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        // Update filename and timestamp
        const filenameElement = document.getElementById('videoFilename');
        const timestampElement = document.getElementById('videoTimestamp');
        
        if (filenameElement) {
            filenameElement.textContent = title;
        }
        
        if (timestampElement) {
            timestampElement.textContent = new Date().toLocaleString('fa-IR');
        }
        
        // Show loading
        this.showLoading();
        this.hideError();
        
        // Reinitialize controls after video loads
        this.video.addEventListener('loadeddata', () => {
            console.log('Video data loaded, reinitializing controls');
            this.reinitializeControls();
        }, { once: true });
        
        // Also reinitialize when video can play
        this.video.addEventListener('canplay', () => {
            console.log('Video can play, ensuring controls work');
            setTimeout(() => {
                this.forceButtonInteractivity();
                this.setupControlButtons();
            }, 200);
        }, { once: true });
    }
    
    // Setup modal cleanup when modal is closed
    setupModalCleanup() {
        const modalEl = document.getElementById('videoPlayerModal');
        if (modalEl) {
            // Prevent duplicate setup
            if (modalEl._cleanupListener && modalEl._cleanupListener._isSetup) {
                console.log('⚠️ Modal cleanup already set up, skipping duplicate setup');
                return;
            }
            
            // Remove existing listener if any
            if (modalEl._cleanupListener) {
                modalEl.removeEventListener('hidden.bs.modal', modalEl._cleanupListener);
            }
            
            // Create cleanup function
            const cleanupFunction = () => {
                try {
                    console.log('Video player modal cleanup started');
                    
                    // Pause video
                    if (this.video) {
                        this.video.pause();
                        this.video.currentTime = 0;
                    }
                    
                    // Stop update interval
                    this.stopUpdateInterval();
                    
                    // Hide overlays
                    this.hideLoading();
                    this.hideError();
                    
                    // Reset progress
                    this.updateProgress();
                    this.updateTimeDisplay();
                    
                    console.log('Video player modal cleanup completed');
                    
                } catch (error) {
                    console.warn('Error during video player modal cleanup:', error);
                }
            };
            
            // Mark cleanup function as set up
            cleanupFunction._isSetup = true;
            
            // Add cleanup listener
            modalEl.addEventListener('hidden.bs.modal', cleanupFunction);
            modalEl._cleanupListener = cleanupFunction;
            
            console.log('Video player modal cleanup setup completed');
        }
    }
    
    destroy() {
        this.stopUpdateInterval();
        this.video?.remove();
        this.controls?.remove();
    }

    // Reinitialize controls after video loads
    reinitializeControls() {
        try {
            console.log('Reinitializing video controls...');
            
            // Force button interactivity
            this.forceButtonInteractivity();
            
            // Setup control buttons
            this.setupControlButtons();
            
            // Update progress and time display
            this.updateProgress();
            this.updateTimeDisplay();
            
            console.log('Video controls reinitialized successfully');
            
        } catch (error) {
            console.warn('Error reinitializing controls:', error);
        }
    }

    // Debug method to check element availability
    debugElements() {
        console.log('=== Video Player Elements Debug ===');
        console.log('Video:', this.video ? '✅ Found' : '❌ Not found');
        console.log('Controls:', this.controls ? '✅ Found' : '❌ Not found');
        console.log('Progress Bar:', this.progressBar ? '✅ Found' : '❌ Not found');
        console.log('Progress Fill:', this.progressFill ? '✅ Found' : '❌ Not found');
        console.log('Progress Handle:', this.progressHandle ? '✅ Found' : '❌ Not found');
        console.log('Current Time:', this.currentTime ? '✅ Found' : '❌ Not found');
        console.log('Duration:', this.duration ? '✅ Found' : '❌ Not found');
        console.log('Play/Pause Button:', this.playPauseBtn ? '✅ Found' : '❌ Not found');
        console.log('Volume Button:', this.volumeBtn ? '✅ Found' : '❌ Not found');
        console.log('Fullscreen Button:', this.fullscreenBtn ? '✅ Found' : '❌ Not found');
        console.log('Loading Overlay:', this.loadingOverlay ? '✅ Found' : '❌ Not found');
        console.log('Error Overlay:', this.errorOverlay ? '✅ Found' : '❌ Not found');
        console.log('Retry Button:', this.retryBtn ? '✅ Found' : '❌ Not found');
        console.log('================================');
    }

    // Setup control buttons with proper event handling
    setupControlButtons() {
        console.log('Setting up control buttons...');
        
        // Play/Pause button
        if (this.playPauseBtn) {
            console.log('Setting up play/pause button');
            // Remove any existing listeners
            this.playPauseBtn.replaceWith(this.playPauseBtn.cloneNode(true));
            this.playPauseBtn = document.getElementById('playPauseBtn');
            
            this.playPauseBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Play/Pause button clicked');
                this.togglePlayPause();
            };
            this.playPauseBtn.style.pointerEvents = 'auto';
            this.playPauseBtn.style.cursor = 'pointer';
            this.playPauseBtn.style.zIndex = '1001';
        } else {
            console.warn('Play/Pause button not found');
        }
        
        // Volume button
        if (this.volumeBtn) {
            console.log('Setting up volume button');
            // Remove any existing listeners
            this.volumeBtn.replaceWith(this.volumeBtn.cloneNode(true));
            this.volumeBtn = document.getElementById('volumeBtn');
            
            this.volumeBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Volume button clicked');
                this.toggleMute();
            };
            this.volumeBtn.style.pointerEvents = 'auto';
            this.volumeBtn.style.cursor = 'pointer';
            this.volumeBtn.style.zIndex = '1001';
        } else {
            console.warn('Volume button not found');
        }
        
        // Fullscreen button
        if (this.fullscreenBtn) {
            console.log('Setting up fullscreen button');
            // Remove any existing listeners
            this.fullscreenBtn.replaceWith(this.fullscreenBtn.cloneNode(true));
            this.fullscreenBtn = document.getElementById('fullscreenBtn');
            
            this.fullscreenBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Fullscreen button clicked');
                this.toggleFullscreen();
            };
            this.fullscreenBtn.style.pointerEvents = 'auto';
            this.fullscreenBtn.style.cursor = 'pointer';
            this.fullscreenBtn.style.zIndex = '1001';
        } else {
            console.warn('Fullscreen button not found');
        }
        
        // Retry button
        if (this.retryBtn) {
            console.log('Setting up retry button');
            // Remove any existing listeners
            this.retryBtn.replaceWith(this.retryBtn.cloneNode(true));
            this.retryBtn = document.getElementById('retryVideoBtn');
            
            this.retryBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Retry button clicked');
                this.retryVideo();
            };
            this.retryBtn.style.pointerEvents = 'auto';
            this.retryBtn.style.cursor = 'pointer';
            this.retryBtn.style.zIndex = '1001';
        } else {
            console.warn('Retry button not found');
        }
        
        console.log('Control buttons setup completed');
    }

    // Activate controls when modal is shown
    activateModalControls() {
        console.log('Activating modal controls...');
        
        // Force controls to be visible and interactive
        if (this.controls) {
            this.controls.style.opacity = '1';
            this.controls.style.visibility = 'visible';
            this.controls.style.pointerEvents = 'auto';
            this.controls.style.zIndex = '1000';
            this.controls.style.display = 'block';
        }
        
        // Focus video element for keyboard controls
        if (this.video) {
            this.video.focus();
            this.video.setAttribute('tabindex', '0');
        }
        
        // Ensure all control buttons are accessible
        const controlButtons = this.controls?.querySelectorAll('.control-btn');
        if (controlButtons) {
            controlButtons.forEach((btn, index) => {
                btn.setAttribute('tabindex', '0');
                btn.style.pointerEvents = 'auto';
                btn.style.cursor = 'pointer';
                btn.style.zIndex = '1001';
                btn.style.opacity = '1';
                btn.style.visibility = 'visible';
                console.log(`Button ${index} activated:`, btn.id || btn.className);
            });
        }
        
        // Re-setup control buttons to ensure events are bound
        setTimeout(() => {
            this.setupControlButtons();
            console.log('Control buttons re-setup completed in modal');
        }, 100);
        
        // Force click events to work
        this.forceButtonInteractivity();
        
        console.log('Modal controls activation completed');
    }
    
    // Force button interactivity
    forceButtonInteractivity() {
        console.log('Forcing button interactivity...');
        
        // Force all buttons to be clickable
        const buttons = [
            this.playPauseBtn,
            this.volumeBtn,
            this.fullscreenBtn,
            this.retryBtn
        ];
        
        buttons.forEach((btn, index) => {
            if (btn) {
                // Force styles
                btn.style.pointerEvents = 'auto';
                btn.style.cursor = 'pointer';
                btn.style.zIndex = '1001';
                btn.style.opacity = '1';
                btn.style.visibility = 'visible';
                btn.style.position = 'relative';
                
                // Remove any disabled attributes
                btn.removeAttribute('disabled');
                btn.removeAttribute('aria-disabled');
                
                // Add click event if not already present
                if (!btn._clickBound) {
                    btn._clickBound = true;
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log(`Button ${index} clicked via force binding`);
                        
                        switch(index) {
                            case 0: this.togglePlayPause(); break;
                            case 1: this.toggleMute(); break;
                            case 2: this.toggleFullscreen(); break;
                            case 3: this.retryVideo(); break;
                        }
                    });
                }
                
                console.log(`Button ${index} forced interactive:`, btn.id || btn.className);
            }
        });
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernVideoPlayer;
} else {
    window.ModernVideoPlayer = ModernVideoPlayer;
} 