import re

with open('static/js/map-core.js', 'r') as f:
    content = f.read()

search = '''                    if (shouldClose) {
                        h.nextElementSibling.classList.add('collapsed'); // Hide content
                        h.querySelector('.toggle-icon').innerText = '▶'; // Reset arrow
                    }
                });
            }'''

replace = '''                    if (shouldClose) {
                        h.nextElementSibling.classList.add('collapsed'); // Hide content
                        h.querySelector('.toggle-icon').innerText = '▶'; // Reset arrow
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
            }'''

if search in content:
    content = content.replace(search, replace)
    with open('static/js/map-core.js', 'w') as f:
        f.write(content)
    print("Successfully patched toggleSection")
else:
    print("toggleSection search string not found")
