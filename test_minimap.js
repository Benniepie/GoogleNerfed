// Leaflet minimaps operate on different map instances.
// We will skip cloning complex active layers as adding them to the minimap
// would require duplicating parsed geojson and setting up custom pane layers.
// As instructed "overlay 'AP Map' & 'SM Map' is fantastic but not essential".
// I will consider the basemap map-core implementation sufficient.
