// Tab switching functionality
function switchTab(tabName) {
  // Remove active class from all tabs and buttons
  document.querySelectorAll(".tab-content").forEach((tab) => {
    tab.classList.remove("active")
  })
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.remove("active")
  })

  // Add active class to selected tab and button
  document.getElementById(tabName + "Tab").classList.add("active")
  event.target.classList.add("active")
}

// File upload handling
document.addEventListener("DOMContentLoaded", () => {
  const uploadForm = document.getElementById("uploadForm")
  const fileInput = document.getElementById("audioFile")
  const uploadButton = document.querySelector(".upload-button")
  const progressDiv = document.getElementById("uploadProgress")
  const progressMessage = document.getElementById("progressMessage")

  if (uploadForm) {
    uploadForm.addEventListener("submit", (e) => {
      if (!fileInput.files[0]) {
        e.preventDefault()
        alert("Please select an audio file to upload.")
        return
      }

      // Show progress
      progressDiv.style.display = "block"
      progressMessage.textContent = "Uploading audio file..."
      uploadButton.disabled = true
      uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...'

      // Update progress messages
      setTimeout(() => {
        progressMessage.textContent = "Processing transcription..."
      }, 1000)

      setTimeout(() => {
        progressMessage.textContent = "Analyzing transcript..."
      }, 3000)
    })
  }

  // File input change handler
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0]
      if (file) {
        const allowedTypes = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
        const fileExt = "." + file.name.split(".").pop().toLowerCase()

        if (!allowedTypes.includes(fileExt)) {
          alert(`File type ${fileExt} not supported. Please upload: ${allowedTypes.join(", ")}`)
          fileInput.value = ""
          return
        }

        if (file.size > 100 * 1024 * 1024) {
          // 100MB
          alert("File size must be less than 100MB")
          fileInput.value = ""
          return
        }

        uploadButton.textContent = `Upload ${file.name}`
      }
    })
  }
})

// Delete call log function
function deleteCallLog(index) {
  if (confirm("Are you sure you want to delete this call log?")) {
    fetch(`/delete_log/${index}`, {
      method: "POST",
    })
      .then((response) => {
        if (response.ok) {
          location.reload()
        } else {
          alert("Failed to delete call log")
        }
      })
      .catch((error) => {
        console.error("Error:", error)
        alert("Failed to delete call log")
      })
  }
}

// Auto-hide flash messages
document.addEventListener("DOMContentLoaded", () => {
  const flashMessages = document.querySelectorAll(".flash-message")
  flashMessages.forEach((message) => {
    setTimeout(() => {
      message.style.opacity = "0"
      setTimeout(() => {
        message.remove()
      }, 300)
    }, 5000)
  })
})

// Audio controls
document.addEventListener("DOMContentLoaded", () => {
  const audioPlayer = document.getElementById("audioPlayer")
  if (!audioPlayer) return // Exit if no audio player (upload page)

  const playBtn = document.getElementById("playBtn")
  const skipBackBtn = document.getElementById("skipBackBtn")
  const skipForwardBtn = document.getElementById("skipForwardBtn")
  const currentTimeEl = document.querySelector(".current-time")
  const totalTimeEl = document.querySelector(".total-time")
  const adityaPlayhead = document.getElementById("adityaPlayhead")
  const arifPlayhead = document.getElementById("arifPlayhead")
  const adityaProgress = document.getElementById("adityaProgress")
  const arifProgress = document.getElementById("arifProgress")
  const speedValue = document.getElementById("speedValue")
  const speedOptions = document.getElementById("speedOptions")
  const volumeIcon = document.getElementById("volumeIcon")
  const volumeSlider = document.getElementById("volumeSlider")
  const volumeLevel = document.getElementById("volumeLevel")
  const volumeHandle = document.getElementById("volumeHandle")
  const transcriptItems = document.querySelectorAll(".transcript-item")
  const adityaTimeline = document.getElementById("adityaTimeline")
  const arifTimeline = document.getElementById("arifTimeline")

  let isPlaying = false
  let currentSpeed = 1
  let volume = 0.8

  // Initialize audio
  audioPlayer.volume = volume

  // Format time helper function
  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${minutes}:${secs.toString().padStart(2, "0")}`
  }

  // Update UI when audio metadata is loaded
  audioPlayer.addEventListener("loadedmetadata", () => {
    totalTimeEl.textContent = formatTime(audioPlayer.duration)
  })

  // Handle play/pause button
  if (playBtn) {
    playBtn.addEventListener("click", () => {
      if (audioPlayer.paused) {
        audioPlayer.play()
      } else {
        audioPlayer.pause()
      }
    })
  }

  // Update UI when play state changes
  audioPlayer.addEventListener("play", () => {
    const icon = playBtn.querySelector("i")
    icon.classList.remove("fa-play")
    icon.classList.add("fa-pause")
    isPlaying = true
  })

  audioPlayer.addEventListener("pause", () => {
    const icon = playBtn.querySelector("i")
    icon.classList.remove("fa-pause")
    icon.classList.add("fa-play")
    isPlaying = false
  })

  // Skip backward 10 seconds
  if (skipBackBtn) {
    skipBackBtn.addEventListener("click", () => {
      audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 10)
    })
  }

  // Skip forward 10 seconds
  if (skipForwardBtn) {
    skipForwardBtn.addEventListener("click", () => {
      audioPlayer.currentTime = Math.min(audioPlayer.duration, audioPlayer.currentTime + 10)
    })
  }

  // Update time display and playhead position
  audioPlayer.addEventListener("timeupdate", () => {
    // Update current time display
    if (currentTimeEl) {
      currentTimeEl.textContent = formatTime(audioPlayer.currentTime)
    }

    if (audioPlayer.duration) {
      // Calculate progress percentage
      const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100

      // Update playheads if they exist
      if (adityaPlayhead) adityaPlayhead.style.left = `${progress}%`
      if (arifPlayhead) arifPlayhead.style.left = `${progress}%`

      // Update progress bars if they exist
      if (adityaProgress) adityaProgress.style.width = `${progress}%`
      if (arifProgress) arifProgress.style.width = `${progress}%`

      // Highlight current transcript segment
      highlightCurrentTranscriptSegment(audioPlayer.currentTime * 1000)
    }
  })

  // Speed control functionality
  if (speedValue) {
    speedValue.addEventListener("click", () => {
      speedOptions.classList.toggle("show")
    })

    // Handle clicking outside speed options to close dropdown
    document.addEventListener("click", (e) => {
      if (!speedValue.contains(e.target)) {
        speedOptions.classList.remove("show")
      }
    })

    // Set playback speed
    document.querySelectorAll(".speed-option").forEach((option) => {
      option.addEventListener("click", () => {
        const speed = Number.parseFloat(option.dataset.speed)
        audioPlayer.playbackRate = speed
        currentSpeed = speed
        speedValue.textContent = `${speed}x`

        // Update active class
        document.querySelectorAll(".speed-option").forEach((opt) => {
          opt.classList.remove("active")
        })
        option.classList.add("active")

        // Hide dropdown
        speedOptions.classList.remove("show")
      })
    })
  }

  // Volume control functionality
  if (volumeIcon) {
    volumeIcon.addEventListener("click", () => {
      if (audioPlayer.volume > 0) {
        audioPlayer.volume = 0
        volumeIcon.className = "fas fa-volume-mute"
        updateVolumeUI(0)
      } else {
        audioPlayer.volume = volume
        updateVolumeIcon(volume)
        updateVolumeUI(volume)
      }
    })
  }

  // Update volume icon based on level
  function updateVolumeIcon(vol) {
    if (!volumeIcon) return

    if (vol === 0) {
      volumeIcon.className = "fas fa-volume-mute"
    } else if (vol < 0.5) {
      volumeIcon.className = "fas fa-volume-down"
    } else {
      volumeIcon.className = "fas fa-volume-up"
    }
  }

  // Update volume UI
  function updateVolumeUI(vol) {
    if (volumeLevel) volumeLevel.style.width = `${vol * 100}%`
    if (volumeHandle) volumeHandle.style.left = `${vol * 100}%`
  }

  // Volume slider interaction
  if (volumeSlider) {
    volumeSlider.addEventListener("click", (e) => {
      const rect = volumeSlider.getBoundingClientRect()
      const pos = (e.clientX - rect.left) / rect.width
      const newVolume = Math.min(Math.max(pos, 0), 1)

      audioPlayer.volume = newVolume
      volume = newVolume
      updateVolumeUI(newVolume)
      updateVolumeIcon(newVolume)
    })
  }

  // Timeline seeking functionality
  const seekAudio = (e, timeline) => {
    const rect = timeline.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    const seekTime = Math.min(Math.max(pos, 0), 1) * audioPlayer.duration
    audioPlayer.currentTime = seekTime
  }

  // Add click event listeners to timelines
  if (adityaTimeline) {
    adityaTimeline.addEventListener("click", (e) => seekAudio(e, adityaTimeline))
  }

  if (arifTimeline) {
    arifTimeline.addEventListener("click", (e) => seekAudio(e, arifTimeline))
  }

  // Handle audio errors
  audioPlayer.addEventListener("error", () => {
    console.error("Error loading audio file")
    alert("Error loading audio file. Please try again or use a different file.")
  })

  // Highlight current transcript segment
  function highlightCurrentTranscriptSegment(currentTimeMs) {
    if (!transcriptItems || transcriptItems.length === 0) return

    let activeSegment = null

    transcriptItems.forEach((item) => {
      // Remove active class first
      item.classList.remove("active")

      // Get start and end times
      const start = Number.parseFloat(item.dataset.start)
      const end = Number.parseFloat(item.dataset.end)

      // Check if current time is within this segment
      if (currentTimeMs >= start && currentTimeMs <= end) {
        activeSegment = item
      }
    })

    // Add active class to current segment and scroll into view
    if (activeSegment) {
      activeSegment.classList.add("active")

      // Optional: scroll to make active segment visible
      // activeSegment.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }
})

// Jump to specific time in transcript
function jumpToTime(time) {
  const audioPlayer = document.getElementById("audioPlayer")
  if (audioPlayer) {
    audioPlayer.currentTime = time
    if (audioPlayer.paused) {
      audioPlayer.play()
    }
  }
}

// Theme toggle functionality
document.addEventListener("DOMContentLoaded", () => {
  const themeToggleBtn = document.getElementById("themeToggleBtn")
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const currentTheme = document.body.getAttribute("data-theme") || "light"
      const newTheme = currentTheme === "dark" ? "light" : "dark"

      document.body.setAttribute("data-theme", newTheme)
      localStorage.setItem("theme", newTheme)

      // Update icon
      const icon = themeToggleBtn.querySelector("i")
      if (newTheme === "dark") {
        icon.classList.remove("fa-moon")
        icon.classList.add("fa-sun")
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i> Switch Theme'
      } else {
        icon.classList.remove("fa-sun")
        icon.classList.add("fa-moon")
        themeToggleBtn.innerHTML = '<i class="fas fa-moon"></i> Switch Theme'
      }
    })

    // Check for saved theme preference
    const savedTheme = localStorage.getItem("theme")
    if (savedTheme) {
      document.body.setAttribute("data-theme", savedTheme)

      if (savedTheme === "dark") {
        const icon = themeToggleBtn.querySelector("i")
        icon.classList.remove("fa-moon")
        icon.classList.add("fa-sun")
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i> Switch Theme'
      }
    }
  }
})
