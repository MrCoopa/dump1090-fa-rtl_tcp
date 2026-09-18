import re, sys, glob

def patch_ol_custom(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "Polygon:il" in content:
        return True

    new_content, count = re.subn(
        r'lE=\{LineString:(\w+),Point:(\w+),MultiPoint:(\w+)\}',
        r'lE={LineString:\1,Point:\2,MultiPoint:\3,Polygon:il}',
        content
    )

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully enabled ol.geom.Polygon in {file_path}!")
        return True
    return False

def patch_script_js(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "function drawOutlineJson" not in content:
        return False

    orig_len = len(content)

    # 1. Declare global variables right where actualOutline is declared
    if "let polarRangeFeatures" not in content:
        content, c0 = re.subn(
            r'let actualOutline = \{\};',
            'let actualOutline = {};\nlet polarRangeFeatures = null;\nlet polarRangeLayer = null;',
            content
        )
        if c0 == 0:
            content = "let polarRangeFeatures = null;\nlet polarRangeLayer = null;\n" + content

    # 2. Insert polarRange layer registration with opacity from localStorage & slider support
    layer_patch = """        layers.push(actualOutline.layer);

        if (!polarRangeFeatures) {
            polarRangeFeatures = new ol.source.Vector();
        }
        let savedPolarOpacity = parseFloat(localStorage.getItem('polar_range_opacity') || '25');
        polarRangeLayer = new ol.layer.Vector({
            name: 'polarRangeAltitude',
            type: 'overlay',
            title: 'altitude range rings (by flight level)',
            source: polarRangeFeatures,
            zIndex: 100,
            renderBuffer: renderBuffer,
            opacity: savedPolarOpacity / 100,
            visible: true,
        });
        layers.push(polarRangeLayer);
        setupPolarOpacityControl();"""

    if "layers.push(polarRangeLayer)" not in content:
        content, count1 = re.subn(
            r'layers\.push\(actualOutline\.layer\);',
            layer_patch,
            content
        )
        if count1 == 0:
            print(f"Warning: Could not patch layers.push in {file_path}")

    # 3. Replace drawUpintheair with filled polygon styling using tar1090 altitude colors
    upintheair_replacement = """function ensurePolygonConstructor() {
    if (typeof ol !== 'undefined' && ol.format && ol.format.GeoJSON && (!ol.geom || typeof ol.geom.Polygon !== 'function')) {
        try {
            let dummy = new ol.format.GeoJSON().readGeometry({
                type: 'Polygon',
                coordinates: [[[0,0],[1,0],[1,1],[0,0]]]
            });
            if (!ol.geom) ol.geom = {};
            ol.geom.Polygon = dummy.constructor;
        } catch(e) {}
    }
}

function getTar1090AltStyle(alt) {
    let h = 20, s = 88, l = 45;
    if (typeof altitudeColor === 'function') {
        try {
            let hsl = altitudeColor(alt);
            h = hsl[0]; s = hsl[1]; l = hsl[2];
        } catch(e) {}
    } else {
        if (alt >= 40000) h = 300;
        else if (alt >= 11000) h = 140 + (300 - 140) * (alt - 11000) / (40000 - 11000);
        else if (alt >= 9000) h = 85 + (140 - 85) * (alt - 9000) / (11000 - 9000);
        else if (alt >= 2000) h = 32.5 + (85 - 32.5) * (alt - 2000) / (9000 - 2000);
    }
    // Fill opacity 0.60; layer-level opacity scales it smoothly from 5% to 80%
    let strokeL = Math.max(10, l - 10);
    return new ol.style.Style({
        fill: new ol.style.Fill({
            color: 'hsla(' + Math.round(h) + ', ' + Math.round(s) + '%, ' + Math.round(l) + '%, 0.60)'
        }),
        stroke: new ol.style.Stroke({
            color: 'hsla(' + Math.round(h) + ', ' + Math.round(s) + '%, ' + strokeL + '%, 0.95)',
            width: 2.0
        })
    });
}

function createClosedGeometry(coords, transform) {
    ensurePolygonConstructor();
    if (typeof ol.geom.Polygon === 'function') {
        try {
            let poly = new ol.geom.Polygon([ coords ]);
            if (transform) {
                poly.transform('EPSG:4326', 'EPSG:3857');
            }
            return poly;
        } catch(e) {}
    }
    let ls = new ol.geom.LineString(coords);
    if (transform) {
        ls.transform('EPSG:4326', 'EPSG:3857');
    }
    return ls;
}

function drawUpintheair() {
    if (!calcOutlineData)
        return;

    let data = calcOutlineData;
    let sortedRings = data.rings.slice().sort((a, b) => b.alt - a.alt);

    for (let i = 0; i < sortedRings.length; ++i) {
        let points = sortedRings[i].points;
        if (!points || points.length === 0) continue;

        let altFt = sortedRings[i].alt * 3.28084;
        let outlineStyle = getTar1090AltStyle(altFt);

        let coords = [];
        for (let j = 0; j < points.length; ++j) {
            coords.push([ points[j][1], points[j][0] ]);
        }
        coords.push([ points[0][1], points[0][0] ]);

        let geom = createClosedGeometry(coords, true);
        let feature = new ol.Feature(geom);
        feature.setStyle(outlineStyle);
        calcOutlineFeatures.addFeature(feature);
    }
}
"""
    content, c_up = re.subn(
        r'function drawUpintheair\(\)\s*\{[\s\S]*?\n\}\n',
        upintheair_replacement,
        content
    )

    # 4. Replace drawOutlineJson with classic single outline + separate polar altitude range
    outline_replacement = """function drawClassicOutlineJson() {
    let request = jQuery.ajax({ url: actualOutline.url,
        cache: false,
        timeout: actualOutline.refresh,
        dataType: 'json' });
    request.done(function(data) {
        actualOutline.features.clear();
        let points = [];
        if (data.multiRange) {
            points = data.multiRange;
        } else if (data.actualRange && data.actualRange.last24h) {
            points[0] = data.actualRange.last24h.points;
        } else {
            points[0] = data.points;
        }
        if (!points[0] || !points[0].length)
            return;
        for (let p = 0; p < points.length; ++p) {
            let geom = null;
            let lastLon = null;
            for (let j = 0; j < points[p].length + 1; ++j) {
                const k = j % points[p].length;
                const lat = points[p][k][0];
                const lon = points[p][k][1];
                const proj = ol.proj.fromLonLat([lon, lat]);
                if (!geom || (lastLon && Math.abs(lon - lastLon) > 270)) {
                    geom = new ol.geom.LineString([proj]);
                    actualOutline.features.addFeature(new ol.Feature(geom));
                } else {
                    geom.appendCoordinate(proj);
                }
                lastLon = lon;
            }
        }
    });
}

function drawPolarRangeJson() {
    if (!polarRangeFeatures) {
        polarRangeFeatures = new ol.source.Vector();
    }
    jQuery.ajax({
        url: 'data/polar_range.json',
        cache: false,
        timeout: 15000,
        dataType: 'json'
    }).done(function(data) {
        if (data && data.rings && data.rings.length > 0) {
            polarRangeFeatures.clear();
            let sortedRings = data.rings.slice().sort((a, b) => b.alt - a.alt);
            for (let i = 0; i < sortedRings.length; ++i) {
                let pts = sortedRings[i].points;
                if (!pts || pts.length < 3) continue;
                let coords = [];
                for (let j = 0; j < pts.length; ++j) {
                    coords.push(ol.proj.fromLonLat([ pts[j][1], pts[j][0] ]));
                }
                coords.push(ol.proj.fromLonLat([ pts[0][1], pts[0][0] ]));

                let geom = createClosedGeometry(coords, false);
                let feature = new ol.Feature(geom);
                feature.setStyle(getTar1090AltStyle(sortedRings[i].alt));
                polarRangeFeatures.addFeature(feature);
            }
        }
    });
}

function setupPolarOpacityControl() {
    // 1. Handle slider input changes directly in the layer menu
    jQuery(document).on('input change', '#polar_switcher_slider', function() {
        let val = parseInt(this.value);
        jQuery('#polar_switcher_val').text(val + '%');
        localStorage.setItem('polar_range_opacity', val);
        if (polarRangeLayer) {
            polarRangeLayer.setOpacity(val / 100);
        }
    });

    // 2. Periodic injection and sync with LayerSwitcher menu
    setInterval(function() {
        // Ensure any floating widget is removed from DOM
        jQuery('#polar_opacity_widget').remove();

        let panel = jQuery('.layer-switcher .panel, .layer-switcher');
        if (panel.length && !jQuery('#polar_switcher_slider').length) {
            let target = panel.find('label:contains("altitude range")').first();
            if (target.length) {
                let savedVal = localStorage.getItem('polar_range_opacity') || '25';
                target.parent().after(
                    '<li id="polar_switcher_li" style="padding-left: 24px; margin: 4px 0 8px 0; list-style: none;">' +
                    '<div style="font-size: 11px; display: flex; align-items: center; gap: 8px; opacity: 0.95; color: #eee;">' +
                    '<span style="font-weight: 500;">Opacity:</span>' +
                    '<input type="range" id="polar_switcher_slider" min="5" max="80" value="' + savedVal + '" ' +
                    'style="width: 80px; height: 12px; cursor: pointer; accent-color: #00d2be; vertical-align: middle;">' +
                    '<span id="polar_switcher_val" style="min-width: 28px; font-weight: bold; color: #fff;">' + savedVal + '%</span>' +
                    '</div></li>'
                );
            }
        }
    }, 1000);
}

function drawOutlineJson() {
    drawClassicOutlineJson();
    drawPolarRangeJson();
}
"""
    content, c_out = re.subn(
        r'function drawOutlineJson\(\)\s*\{[\s\S]*?\n\}\n',
        outline_replacement,
        content
    )

    if len(content) < (orig_len - 5000):
        print(f"Error: Truncation guard triggered for {file_path}! Original: {orig_len}, New: {len(content)}")
        return False

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Successfully patched {file_path} (Original: {orig_len}b -> Patched: {len(content)}b)!")
    return True

def patch_file(file_path):
    if "ol-custom" in file_path:
        return patch_ol_custom(file_path)
    else:
        return patch_script_js(file_path)

if __name__ == "__main__":
    for target in sys.argv[1:]:
        for f in glob.glob(target):
            patch_file(f)
