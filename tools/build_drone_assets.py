import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib


PALETTE = [(34, 39, 44), (77, 84, 88), (155, 165, 171), (28, 33, 38), (98, 108, 80), (211, 167, 61), (124, 88, 53), (55, 137, 166)]
PARTS = {'rc-goblin': ['$body', '$blade0', '$blade1', '$blade2', '$blade3'], 'rc-goblin-bomb': ['$body', '$blade0', '$blade1', '$blade2', '$blade3'], 'rv_geran': ['$body', '$blade0'], 'rv_fp1': ['$body', '$blade0']}


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def normalize(a):
    length = math.sqrt(dot(a, a))
    return tuple(v / length for v in a)


def png(path, pixels, width, height):
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)

    rows = b''.join(b'\0' + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def atlas(plane=False):
    pixels = bytearray()
    colors = PALETTE[:]
    if plane:
        colors[4] = (167, 175, 174)
        colors[5] = (186, 150, 75)
    for y in range(256):
        for x in range(256):
            tile, tx = divmod(x, 32)
            color = colors[tile]
            variation = ((x * 17 + y * 23) % 7) - 3
            if tile == 0:
                variation += 6 if ((tx + y) // 3) % 2 else -4
                variation -= 5 if ((tx - y) // 3) % 2 else 0
            elif tile == 1:
                variation += (y % 5) - 2
                variation -= 22 if tx in (6, 7, 24, 25) and 30 < y % 64 < 49 else 0
            elif tile == 2:
                variation += 7 if tx in (3, 28) else (y % 4) - 2
            elif tile == 3:
                variation -= 7 if y % 16 < 3 else 0
                variation += 4 if tx in (3, 28) else 0
            elif tile == 4:
                variation -= 20 if tx in (2, 29) or y % 64 in (1, 2) else 0
                variation += 14 if min((tx - 6) ** 2 + (y % 64 - 9) ** 2, (tx - 25) ** 2 + (y % 64 - 9) ** 2) <= 2 else 0
            elif tile == 5:
                variation -= 23 if tx in (3, 4, 27, 28) else 0
                variation += 5 if y % 10 < 2 else 0
            elif tile == 6:
                variation -= 16 if y % 80 in (10, 11, 12) else 0
                variation += 4 if tx % 8 == 0 else 0
            else:
                radius = ((tx - 15.5) / 15.5) ** 2 + ((y - 128) / 128) ** 2
                glow = max(0, 1 - radius)
                color = (int(17 + 37 * glow), int(36 + 105 * glow), int(53 + 119 * glow))
                variation += 48 if abs((tx / 32) - (y / 256) * .36 - .30) < .055 else 0
            pixels.extend(max(0, min(255, value + variation)) for value in color)
            pixels.append(255)
    return pixels


class Mesh:
    def __init__(self):
        self.parts = {}
        self.solids = []

    def face(self, points, color, center, part='$body'):
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        middle = tuple(sum(p[i] for p in points) / len(points) for i in range(3))
        if dot(normal, sub(middle, center)) < 0:
            points = points[::-1]
        data = self.parts.setdefault(part, {'vertices': [], 'faces': [], 'lookup': {}})
        indices = []
        for point in points:
            key = tuple(round(v, 9) for v in point)
            if key not in data['lookup']:
                data['lookup'][key] = len(data['vertices'])
                data['vertices'].append(tuple(point))
            indices.append(data['lookup'][key])
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        axis = max(range(3), key=lambda i: abs(normal[i]))
        projection = [(p[(axis + 1) % 3], p[(axis + 2) % 3]) for p in points]
        minima = [min(p[i] for p in projection) for i in range(2)]
        extents = [max(p[i] for p in projection) - minima[i] for i in range(2)]
        uv = [((color + .10 + .8 * (p[0] - minima[0]) / max(extents[0], 1e-9)) / 8, .07 + .86 * (p[1] - minima[1]) / max(extents[1], 1e-9)) for p in projection]
        data['faces'].append({'indices': indices, 'color': color, 'uv': uv, 'center': center})

    def solid(self, rings, color=4, part='$body', caps=True, cap_colors=None, side_colors=None):
        center = tuple(sum(p[i] for ring in rings for p in ring) / sum(map(len, rings)) for i in range(3))
        start_faces = len(self.parts.get(part, {}).get('faces', []))
        for row, (a, b) in enumerate(zip(rings, rings[1:])):
            for i in range(len(a)):
                j = (i + 1) % len(a)
                shade = side_colors[row] if side_colors else color
                self.face([a[i], a[j], b[j], b[i]], shade, center, part)
        if caps:
            for side, ring in enumerate((rings[0], rings[-1])):
                shade = cap_colors[side] if cap_colors else color
                if shade is None:
                    continue
                for i in range(1, len(ring) - 1):
                    self.face([ring[0], ring[i], ring[i + 1]], shade, center, part)
        self.solids.append((part, start_faces, len(self.parts[part]['faces']), center))

    def box(self, center, size, color=0, yaw=0, part='$body'):
        x, y, z = center
        a, b, c = [v / 2 for v in size]
        r = math.radians(yaw)
        points = [(x + dx * math.cos(r) + dz * math.sin(r), y + dy, z - dx * math.sin(r) + dz * math.cos(r)) for dx, dy, dz in [(-a, -b, -c), (a, -b, -c), (a, b, -c), (-a, b, -c), (-a, -b, c), (a, -b, c), (a, b, c), (-a, b, c)]]
        for indices in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 4, 7, 3), (1, 2, 6, 5), (0, 1, 5, 4), (3, 7, 6, 2)]:
            self.face([points[i] for i in indices], color, center, part)

    def extrude(self, outline, height, thickness, color=0, plane='xz', part='$body', side_color=None):
        if plane == 'xz':
            rings = [[(x, height + sign * thickness / 2, z) for x, z in outline] for sign in (-1, 1)]
        elif plane == 'yz':
            rings = [[(height + sign * thickness / 2, y, z) for z, y in outline] for sign in (-1, 1)]
        else:
            rings = [[(x, y, height + sign * thickness / 2) for x, y in outline] for sign in (-1, 1)]
        self.solid(rings, color, part, side_colors=[side_color if side_color is not None else color])

    def radial(self, center, profile, color=1, sides=12, axis='y', part='$body', cap_colors=None, side_colors=None):
        if axis == 'y':
            rings = [[(center[0] + radius * math.cos(i * math.tau / sides), center[1] + offset, center[2] + radius * math.sin(i * math.tau / sides)) for i in range(sides)] for offset, radius in profile]
        else:
            rings = [[(center[0] + radius * math.cos(i * math.tau / sides), center[1] + radius * math.sin(i * math.tau / sides), center[2] + offset) for i in range(sides)] for offset, radius in profile]
        self.solid(rings, color, part, cap_colors=cap_colors, side_colors=side_colors)

    def loft(self, profile, color=4, sides=16):
        rings = [[(math.cos(i * math.tau / sides) * rx, y + math.sin(i * math.tau / sides) * ry, z) for i in range(sides)] for z, y, rx, ry in profile]
        self.solid(rings, color)

    def wing(self, stations, y, color=4):
        rings = []
        for x, leading, trailing, thickness in stations:
            chord = leading - trailing
            rings.append([(x, y, leading), (x, y + thickness * .60, leading - chord * .24), (x, y + thickness * .40, leading - chord * .72), (x, y, trailing), (x, y - thickness * .30, leading - chord * .72), (x, y - thickness * .40, leading - chord * .24)])
        self.solid(rings, color)

    def propeller(self, pivot, radius, blades, part, axis='y'):
        for i in range(blades):
            angle = math.tau * i / blades + .18
            points = [(radius * .12, -.012), (radius * .96, .006), (radius, .029), (radius * .28, .026)]
            outline = []
            for span, width in points:
                u = span * math.cos(angle) - width * math.sin(angle)
                v = span * math.sin(angle) + width * math.cos(angle)
                outline.append((pivot[0] + u, pivot[2] + v) if axis == 'y' else (pivot[0] + u, pivot[1] + v))
            self.extrude(outline, pivot[1] if axis == 'y' else pivot[2], .006 if axis == 'y' else .014, 0 if axis == 'y' else 3, 'xz' if axis == 'y' else 'xy', part, 2)
        self.radial(pivot, [(-.008, .012 if axis == 'y' else .035), (.008, .012 if axis == 'y' else .035)], 2, 8 if axis == 'y' else 12, axis, part)

    def audit(self):
        faces = [face for part in self.parts.values() for face in part['faces']]
        points = [point for part in self.parts.values() for point in part['vertices']]
        degenerate = 0
        inward = 0
        minimum_area = math.inf
        colors = set()
        for data in self.parts.values():
            for face in data['faces']:
                positions = [data['vertices'][i] for i in face['indices']]
                normal = cross(sub(positions[1], positions[0]), sub(positions[2], positions[0]))
                area = math.sqrt(dot(normal, normal)) / 2
                minimum_area = min(minimum_area, area)
                degenerate += area <= 1e-10
                middle = tuple(sum(p[i] for p in positions) / len(positions) for i in range(3))
                inward += dot(normal, sub(middle, face['center'])) < -1e-10
                colors.add(face['color'])
                assert len(set(face['indices'])) == len(face['indices'])
                assert all(0 <= u <= 1 and 0 <= v <= 1 for u, v in face['uv'])
                assert len(face['indices']) in (3, 4)
                assert all(math.isfinite(v) for p in positions for v in p)
        assert not degenerate and not inward
        assert len(faces) <= 1200
        assert sum(len(face['indices']) - 2 for face in faces) <= 1200
        return {'faces': len(faces), 'triangles': sum(len(face['indices']) - 2 for face in faces), 'vertices': len(points), 'parts': {name: {'faces': len(data['faces']), 'vertices': len(data['vertices'])} for name, data in self.parts.items()}, 'bounds': [[round(min(p[i] for p in points), 6), round(max(p[i] for p in points), 6)] for i in range(3)], 'materials': sorted(colors), 'degenerate_faces': degenerate, 'inward_faces': inward, 'minimum_triangle_area': minimum_area, 'uv_valid': True, 'finite_vertices': True, 'source_units_per_block': 100}

    def write(self, path):
        report = self.audit()
        lines = ['Metasequoia Document', 'Format Text Ver 1.1', 'Material 1 {', '"RV" shader(3) col(1 1 1 1) dif(0.9) amb(0.25) emi(0) spc(0.15) power(8)', '}']
        for name, data in self.parts.items():
            lines.extend([f'Object "{name}" {{', 'visible 15', 'shading 1', 'facet 45.0', f'vertex {len(data["vertices"])} {{'])
            lines.extend(' '.join(f'{v * 100:.5f}' for v in point) for point in data['vertices'])
            lines.extend(['}', f'face {len(data["faces"])} {{'])
            for face in data['faces']:
                order = [0] + list(range(len(face['indices']) - 1, 0, -1))
                lines.append(f'{len(face["indices"])} V(' + ' '.join(str(face['indices'][i]) for i in order) + ') M(0) UV(' + ' '.join(f'{face["uv"][i][0]:.6f} {face["uv"][i][1]:.6f}' for i in order) + ')')
            lines.extend(['}', '}'])
        lines.append('Eof')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(lines) + '\n', encoding='ascii')
        report['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        return report


def quad(combat):
    mesh = Mesh()
    for x, z in [(-.22, .22), (.22, .22), (-.22, -.22), (.22, -.22)]:
        mesh.box((x / 2, -.006, z / 2), (.043, .022, math.hypot(x, z)), 0, math.degrees(math.atan2(x, z)))
    outline = [(-.066, -.096), (.066, -.096), (.082, -.073), (.082, .079), (.063, .102), (-.063, .102), (-.082, .079), (-.082, -.073)]
    mesh.extrude(outline, .013, .016, 0, side_color=2)
    mesh.extrude([(x * .94, z * .94) for x, z in outline], .052, .012, 0, side_color=1)
    for x in [-.057, .057]:
        for z in [-.070, .067]:
            mesh.box((x, .033, z), (.011, .024, .011), 6)
    battery = [(-.051, -.119), (.051, -.119), (.061, -.109), (.061, .050), (.051, .060), (-.051, .060), (-.061, .050), (-.061, -.109)]
    mesh.extrude(battery, .103, .072, 3, side_color=1)
    for z in [-.083, .022]:
        mesh.box((0, .142, z), (.126, .009, .019), 5)
        for x in [-.065, .065]:
            mesh.box((x, .102, z), (.009, .076, .019), 5)
    mesh.box((0, .038, .127), (.074, .062, .049), 1)
    for x in [-.047, .047]:
        mesh.box((x, .032, .113), (.018, .067, .054), 6)
    mesh.radial((0, .044, .160), [(-.010, .027), (.012, .023)], 3, 12, 'z', cap_colors=[None, 3])
    mesh.radial((0, .044, .175), [(-.003, .0175), (.003, .0175)], 7, 12, 'z', cap_colors=[None, 7], side_colors=[1])
    mesh.box((0, .062, -.137), (.051, .018, .030), 6)
    mesh.box((.038, .092, -.148), (.011, .079, .012), 3)
    mesh.radial((.038, .148, -.148), [(-.020, .0045), (.020, .0045)], 1, 6)
    mesh.radial((.038, .170, -.148), [(-.007, .013), (.007, .013)], 3, 8)
    for x in [-.022, .022]:
        mesh.box((x, .064, -.161), (.006, .007, .070), 3, 15 if x > 0 else -15)
    for i, (x, z) in enumerate([(-.22, .22), (.22, .22), (-.22, -.22), (.22, -.22)]):
        mesh.radial((x, .037, z), [(-.026, .028), (-.013, .035), (.033, .025)], 1, 12, side_colors=[2, 1], cap_colors=[1, 2])
        mesh.box((x, -.028, z), (.027, .062, .030), 3)
        mesh.box((x, -.060, z), (.036, .014, .040), 6)
        mesh.propeller((x, .09, z), .135, 3, f'$blade{i}')
    if combat:
        mesh.box((0, -.027, -.005), (.068, .049, .105), 1)
        mesh.radial((0, -.099, .002), [(-.099, .030), (-.070, .044), (.060, .044), (.087, .020)], 6, 10, 'z', side_colors=[1, 6, 6], cap_colors=[1, 2])
        for z in [-.045, .033]:
            mesh.box((0, -.044, z), (.094, .012, .018), 5)
    return mesh


def geran():
    mesh = Mesh()
    mesh.wing([(-1.43, -1.01, -1.19, .025), (-.80, -.14, -1.16, .065), (0, .94, -1.11, .090), (.80, -.14, -1.16, .065), (1.43, -1.01, -1.19, .025)], .20)
    mesh.loft([(-1.17, .245, .092, .096), (-.86, .245, .193, .162), (-.25, .245, .203, .169), (.42, .245, .177, .151), (.91, .245, .087, .078), (1.19, .245, .012, .013)], 4, 16)
    for sign in [-1, 1]:
        mesh.extrude([(-1.19, .20), (-1.00, .20), (-1.01, .59), (-1.10, .65), (-1.18, .62)], sign * 1.42, .029, 4, 'yz', side_color=1)
        mesh.box((sign * .074, .36, -.42), (.009, .025, .19), 1)
    mesh.box((0, .417, -.12), (.050, .014, .195), 1)
    mesh.radial((0, .20, -1.20), [(-.083, .066), (.051, .076)], 1, 12, 'z')
    mesh.propeller((0, .20, -1.34), .39, 2, '$blade0', 'z')
    return mesh


def fp1():
    mesh = Mesh()
    mesh.loft([(-.70, .29, .103, .112), (-.49, .29, .197, .183), (-.09, .29, .230, .213), (.49, .29, .208, .193), (.89, .29, .127, .124), (1.19, .29, .041, .050), (1.31, .29, .011, .014)], 4, 16)
    mesh.wing([(-1.80, .37, -.22, .036), (-1.35, .46, -.24, .065), (0, .49, -.25, .072), (1.35, .46, -.24, .065), (1.80, .37, -.22, .036)], .425)
    for x in [-.48, .48]:
        mesh.radial((x, .29, -.82), [(-.86, .022), (-.53, .026), (.36, .038), (.54, .022)], 1, 8, 'z')
        mesh.extrude([(-1.76, .30), (-1.43, .30), (-1.46, .69), (-1.56, .80), (-1.72, .76)], x, .028, 4, 'yz', side_color=1)
    mesh.wing([(-.65, -1.43, -1.77, .022), (0, -1.40, -1.78, .032), (.65, -1.43, -1.77, .022)], .322)
    mesh.box((0, .497, .20), (.058, .015, .187), 1)
    mesh.box((0, .515, -.01), (.008, .075, .023), 3)
    mesh.radial((0, .28, -.75), [(-.070, .071), (.064, .095)], 1, 12, 'z')
    mesh.propeller((0, .28, -.91), .42, 2, '$blade0', 'z')
    return mesh


def render_icon(mesh, texture, size=64, supersample=3, elevation=48, azimuth=25):
    width = size * supersample
    az, el = math.radians(azimuth), math.radians(elevation)
    right = (math.cos(az), 0, -math.sin(az))
    up = (-math.sin(az) * math.sin(el), math.cos(el), -math.cos(az) * math.sin(el))
    toward = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    points = [p for data in mesh.parts.values() for p in data['vertices']]
    xs, ys = [dot(p, right) for p in points], [dot(p, up) for p in points]
    center_x, center_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    scale = width * .88 / max(max(xs) - min(xs), max(ys) - min(ys))
    pixels = bytearray(width * width * 4)
    depths = [-math.inf] * (width * width)
    light = normalize((-.35, 1, .60))
    for data in mesh.parts.values():
        for face in data['faces']:
            points = [data['vertices'][i] for i in face['indices']]
            normal = normalize(cross(sub(points[1], points[0]), sub(points[2], points[0])))
            if dot(normal, toward) <= 0:
                continue
            shade = .52 + .48 * max(0, dot(normal, light))
            positions = [((dot(p, right) - center_x) * scale + width / 2, width / 2 - (dot(p, up) - center_y) * scale, dot(p, toward)) for p in points]
            for k in range(1, len(points) - 1):
                vertices = [positions[i] for i in (0, k, k + 1)]
                uvs = [face['uv'][i] for i in (0, k, k + 1)]
                (ax, ay, _), (bx, by, _), (cx, cy, _) = vertices
                denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(denominator) < 1e-9:
                    continue
                for y in range(max(0, int(min(p[1] for p in vertices))), min(width, math.ceil(max(p[1] for p in vertices)) + 1)):
                    for x in range(max(0, int(min(p[0] for p in vertices))), min(width, math.ceil(max(p[0] for p in vertices)) + 1)):
                        a = ((by - cy) * (x + .5 - cx) + (cx - bx) * (y + .5 - cy)) / denominator
                        b = ((cy - ay) * (x + .5 - cx) + (ax - cx) * (y + .5 - cy)) / denominator
                        c = 1 - a - b
                        if min(a, b, c) < -1e-7:
                            continue
                        weights = (a, b, c)
                        depth = sum(weights[i] * vertices[i][2] for i in range(3))
                        offset = y * width + x
                        if depth <= depths[offset]:
                            continue
                        depths[offset] = depth
                        u, v = [sum(weights[i] * uvs[i][axis] for i in range(3)) for axis in range(2)]
                        sample = (min(255, int(v * 256)) * 256 + min(255, int(u * 256))) * 4
                        pixels[offset * 4:offset * 4 + 4] = bytes([round(texture[sample + i] * shade) for i in range(3)] + [255])
    reduced = bytearray()
    for y in range(size):
        for x in range(size):
            offsets = [((y * supersample + dy) * width + x * supersample + dx) * 4 for dy in range(supersample) for dx in range(supersample)]
            visible = [offset for offset in offsets if pixels[offset + 3]]
            if visible:
                reduced.extend(round(sum(pixels[offset + i] for offset in visible) / len(visible)) for i in range(3))
                reduced.append(round(255 * len(visible) / len(offsets)))
            else:
                reduced.extend((0, 0, 0, 0))
    return reduced


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'patches/controls/resources/assets/mcheli')
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    report = {}
    meshes = [('rc-goblin', quad(False), 'helicopters'), ('rc-goblin-bomb', quad(True), 'helicopters'), ('rv_geran', geran(), 'planes'), ('rv_fp1', fp1(), 'planes')]
    for name, mesh, folder in meshes:
        assert list(mesh.parts) == PARTS[name]
        report[name] = mesh.write(args.output / 'models' / folder / (name + '.mqo'))
        report[name]['native_triangle_count'] = report[name]['triangles']
        report[name]['mqo_winding'] = 'clockwise; native loader reverses face indices'
        if folder == 'helicopters':
            report[name]['pivots'] = {f'$blade{i}': {'position': [x, .09, z], 'axis': [0, 1, 0]} for i, (x, z) in enumerate([(-.22, .22), (.22, .22), (-.22, -.22), (.22, -.22)])}
        else:
            report[name]['pivots'] = {'$blade0': {'position': [0, .20, -1.34] if name == 'rv_geran' else [0, .28, -.91], 'axis': [0, 0, 1]}}
        texture = atlas(name == 'rv_fp1')
        texture_path = args.output / 'textures' / folder / (name + '.png')
        png(texture_path, texture, 256, 256)
        icon = render_icon(mesh, texture, elevation=30 if name == 'rc-goblin-bomb' else 48)
        icon_path = args.output / 'textures/items' / (name + '.png')
        png(icon_path, icon, 64, 64)
        report[name]['texture_sha256'] = hashlib.sha256(texture_path.read_bytes()).hexdigest()
        report[name]['icon_sha256'] = hashlib.sha256(icon_path.read_bytes()).hexdigest()
        report[name]['icon_visible_pixels'] = sum(bool(icon[i]) for i in range(3, len(icon), 4))
        if args.preview:
            png(args.preview / (name + '.png'), render_icon(mesh, texture, 384, 1), 384, 384)
    for name in ['rc-goblin-1', 'rc-goblin-2', 'rc-goblin-bomb-1']:
        png(args.output / 'textures/helicopters' / (name + '.png'), atlas(), 256, 256)
    report_path = args.output / 'rv-models.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
