<<<<<<< SEARCH
            // 2. Auto-close logic
            if (isOpening) {
                const allHeaders = document.querySelectorAll('.section-header');
                allHeaders.forEach(h => {
                    const name = h.innerText.trim();
                    if (h === header) return;

                    let shouldClose = false;
                    if (sectionName.includes('Front Line') && name.includes('Static')) shouldClose = true;
                    if (sectionName.includes('Map Admin') && (name.includes('Front Line') || name.includes('Base Map') || name.includes('Static'))) shouldClose = true;

                    if (shouldClose) {
                        h.nextElementSibling.classList.add('collapsed');
                        h.querySelector('.toggle-icon').innerText = '▶';
                    }
                });
            }
=======
            // 2. Auto-close logic
            if (isOpening) {
                const allHeaders = document.querySelectorAll('.section-header');
                allHeaders.forEach(h => {
                    const name = h.innerText.trim();
                    if (h === header) return;

                    let shouldClose = false;
                    if (sectionName.includes('Front Line') && name.includes('Static')) shouldClose = true;
                    if (sectionName.includes('Map Admin') && (name.includes('Front Line') || name.includes('Base Map') || name.includes('Static'))) shouldClose = true;

                    if (shouldClose) {
                        h.nextElementSibling.classList.add('collapsed');
                        h.querySelector('.toggle-icon').innerText = '▶';
                    }
                });

                // If opening Front Line Tracker, preload a few layers
                if (sectionName.includes('Front Line')) {
                    if (window.availableDates && window.availableDates.length > 0) {
                        const slider = document.getElementById('timelineSlider');
                        if (slider) {
                            slider.dispatchEvent(new Event('input'));
                        }
                    }
                }
            }
