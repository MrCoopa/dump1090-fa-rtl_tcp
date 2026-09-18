import re, sys, glob

def patch_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "function drawOutlineJson" not in content:
        print(f"Warning: function drawOutlineJson not found in {file_path}")
        return False

    replacement = """function getTar1090AltStyle(alt) {
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

        let geom = new ol.geom.Polygon([ coords ]);
        geom.transform('EPSG:4326', 'EPSG:3857');

        let feature = new ol.Feature(geom);
        feature.setStyle(outlineStyle);
        calcOutlineFeatures.addFeature(feature);
    }
}

function drawPolarPolygons(rings) {
    actualOutline.features.clear();
    let sortedRings = rings.slice().sort((a, b) => b.alt - a.alt);
    for (let i = 0; i < sortedRings.length; ++i) {
        let pts = sortedRings[i].points;
        if (!pts || pts.length < 3) continue;
        let coords = [];
        for (let j = 0; j < pts.length; ++j) {
            coords.push(ol.proj.fromLonLat([ pts[j][1], pts[j][0] ]));
        }
        coords.push(ol.proj.fromLonLat([ pts[0][1], pts[0][0] ]));
        let geom = new ol.geom.Polygon([ coords ]);
        let feature = new ol.Feature(geom);
        feature.setStyle(getTar1090AltStyle(sortedRings[i].alt));
        actualOutline.features.addFeature(feature);
    }
}

function fallbackOutlineJson() {
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

function drawOutlineJson() {
    jQuery.ajax({
        url: 'data/polar_range.json',
        cache: false,
        timeout: actualOutline.refresh,
        dataType: 'json'
    }).done(function(data) {
        if (data && data.rings && data.rings.length > 0) {
            drawPolarPolygons(data.rings);
        } else {
            fallbackOutlineJson();
        }
    }).fail(function() {
        fallbackOutlineJson();
    });
}"""

    # Replace drawUpintheair (if present) through drawOutlineJson
    pattern = r'(function drawUpintheair\(\)\s*\{[\s\S]*?\n\}\n\n)?function drawOutlineJson\(\)\s*\{[\s\S]*?\n\}\n'
    new_content, count = re.subn(pattern, replacement + '\n', content)

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully patched {file_path} with tar1090 altitude color scale & polar range support!")
        return True
    else:
        print(f"Pattern matching drawOutlineJson failed in {file_path}")
        return False

if __name__ == "__main__":
    for target in sys.argv[1:]:
        for f in glob.glob(target):
            patch_file(f)
