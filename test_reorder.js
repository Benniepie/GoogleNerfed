const assert = require('assert');

let activeLayers = {
  'SM Map 2024.kml': 'layer_sm',
  'Crimea.kml': 'layer_crimea'
};

// ... Wait, how do active layers behave during re-adding static layers
// The user says:
// 1) The front line map layers are all redrawn which is slow...
// 2) The existing static data layers that I had ticked are unticked and removed from the map
// 3) If the file I've uploaded is a KMZ file it is not included in the layers list and I can't show it on the map.
