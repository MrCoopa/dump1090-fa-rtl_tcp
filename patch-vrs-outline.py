import re, sys, glob

def patch_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "function drawOutlineJson" not in content:
        print(f"Warning: function drawOutlineJson not found in {file_path}")
        return False

    orig_len = len(content)

    # 1. Declare global variables right where actualOutline is declared (BEFORE map initialization)
    if "let polarRangeFeatures" not in content:
        content, c0 = re.subn(
            r'let actualOutline = \{\};',
            'let actualOutline = {};\nlet polarRangeFeatures = null;\nlet polarRangeLayer = null;',
            content
        )
        if c0 == 0:
            content = "let polarRangeFeatures = null;\nlet polarRangeLayer = null;\n" + content

    # 2. Insert polarRange layer registration into layers array alongside actualOutline
    layer_patch = """        layers.push(actualOutline.layer);

        if (!polarRangeFeatures) {
            polarRangeFeatures = new ol.source.Vector();
        }
        polarRangeLayer = new ol.layer.Vector({
            name: 'polarRangeAltitude',
            type: 'overlay',
            title: 'altitude range rings (by flight level)',
            source: polarRangeFeatures,
            zIndex: 100,
            renderBuffer: renderBuffer,
            visible: true,
        });
        layers.push(polarRangeLayer);"""

    if "layers.push(polarRangeLayer)" not in content:
        content, count1 = re.subn(
            r'layers\.push\(actualOutline\.layer\);',
            layer_patch,
            content
        )
        if count1 == 0:
            print(f"Warning: Could not patch layers.push in {file_path}")

    # 3. Replace drawUpintheair with filled polygon styling using tar1090 altitude colors
    upintheair_replacement = """function getTar1090AltStyle(alt) {
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
    let fillAlpha = 0.35;
    let strokeL = Math.max(10, l - 15);
    return new ol.style.Style({
        fill: new ol.style.Fill({
            color: 'hsla(' + Math.round(h) + ', ' + Math.round(s) + '%, ' + Math.round(l) + '%, ' + fillAlpha + ')'
        }),
        stroke: new ol.style.Stroke({
            color: 'hsla(' + Math.round(h) + ', ' + Math.round(s) + '%, ' + strokeL + '%, 0.90)',
            width: 2.0
        })
    });
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

        let geom = new ol.geom.LineString(coords);
        geom.transform('EPSG:4326', 'EPSG:3857');

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
                let geom = new ol.geom.LineString(coords);
                let feature = new ol.Feature(geom);
                feature.setStyle(getTar1090AltStyle(sortedRings[i].alt));
                polarRangeFeatures.addFeature(feature);
            }
        }
    });
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

if __name__ == "__main__":
    for target in sys.argv[1:]:
        for f in glob.glob(target):
            patch_file(f)
