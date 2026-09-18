import re, sys, glob

def patch_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "drawUpintheair" not in content:
        return False

    vrs_function = """function drawUpintheair() {
    if (!calcOutlineData)
        return;

    let data = calcOutlineData;
    let sortedRings = data.rings.slice().sort((a, b) => b.alt - a.alt);

    // VRS-style palette from outermost (highest altitude) to innermost (lowest altitude)
    let fillPalette = [
        { fill: 'rgba(235, 65, 65, 0.40)', stroke: 'rgba(160, 20, 20, 0.90)' },   // 40k ft / Red
        { fill: 'rgba(155, 65, 215, 0.45)', stroke: 'rgba(95, 20, 150, 0.90)' },  // 30k ft / Purple
        { fill: 'rgba(45, 175, 85, 0.50)', stroke: 'rgba(20, 115, 50, 0.90)' },   // 20k ft / Green
        { fill: 'rgba(155, 235, 180, 0.60)', stroke: 'rgba(25, 130, 75, 0.95)' }  // 10k ft / Mint
    ];

    for (let i = 0; i < sortedRings.length; ++i) {
        let points = sortedRings[i].points;
        if (!points || points.length === 0) continue;

        let pal = fillPalette[i % fillPalette.length];
        let outlineStyle = new ol.style.Style({
            fill: new ol.style.Fill({
                color: pal.fill
            }),
            stroke: new ol.style.Stroke({
                color: pal.stroke,
                width: 2.0
            })
        });

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
}"""

    new_content, count = re.subn(
        r'function drawUpintheair\(\)\s*\{[\s\S]*?\n\}\n\nfunction drawOutlineJson',
        vrs_function + '\n\nfunction drawOutlineJson',
        content
    )

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully patched {file_path} for VRS-style colored filled polygons!")
        return True
    else:
        print(f"Pattern not found in {file_path}")
        return False

if __name__ == "__main__":
    for target in sys.argv[1:]:
        for f in glob.glob(target):
            patch_file(f)
