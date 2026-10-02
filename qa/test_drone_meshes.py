import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import zlib


REPO = Path(__file__).resolve().parents[1]
EXPECTED = {'rc-goblin': 'helicopters', 'rc-goblin-bomb': 'helicopters', 'rv_geran': 'planes', 'rv_fp1': 'planes'}


def read_mqo(path):
    text = path.read_text(encoding='ascii')
    assert text.startswith('Metasequoia Document\nFormat Text Ver 1.1\n')
    result = {}
    for match in re.finditer(r'Object "([^"]+)" \{(.*?)(?=\nObject |\nEof)', text, re.S):
        body = match.group(2)
        vertex_match = re.search(r'vertex (\d+) \{\n([^}]+)\}', body)
        face_match = re.search(r'face (\d+) \{\n([^}]+)\}', body)
        vertices = [tuple(float(value) / 100 for value in line.split()) for line in vertex_match.group(2).splitlines()]
        assert len(vertices) == int(vertex_match.group(1))
        faces = []
        for line in face_match.group(2).splitlines():
            face = re.fullmatch(r'(\d+) V\(([\d ]+)\) M\(0\) UV\(([\d. ]+)\)', line)
            assert face, line
            count = int(face.group(1))
            indices = list(map(int, face.group(2).split()))
            values = list(map(float, face.group(3).split()))
            assert count in (3, 4) and len(indices) == count and len(values) == count * 2
            assert all(0 <= value <= 1 for value in values)
            assert all(0 <= index < len(vertices) for index in indices)
            triangles = [[indices[2], indices[1], indices[0]]]
            if count == 4:
                triangles.append([indices[0], indices[3], indices[2]])
            faces.append((indices, values, triangles))
        assert len(faces) == int(face_match.group(1))
        result[match.group(1)] = (vertices, faces)
    return result


def read_png(path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    index = 8
    encoded = bytearray()
    width = height = 0
    while index < len(data):
        length = struct.unpack('>I', data[index:index + 4])[0]
        name = data[index + 4:index + 8]
        payload = data[index + 8:index + 8 + length]
        crc = struct.unpack('>I', data[index + 8 + length:index + 12 + length])[0]
        assert zlib.crc32(name + payload) & 0xffffffff == crc
        if name == b'IHDR':
            width, height, depth, color, compression, filtering, interlacing = struct.unpack('>IIBBBBB', payload)
            assert (depth, color, compression, filtering, interlacing) == (8, 6, 0, 0, 0)
        elif name == b'IDAT':
            encoded.extend(payload)
        index += length + 12
    decoded = zlib.decompress(encoded)
    stride = width * 4 + 1
    assert len(decoded) == height * stride
    assert all(decoded[y * stride] == 0 for y in range(height))
    pixels = b''.join(decoded[y * stride + 1:(y + 1) * stride] for y in range(height))
    return width, height, pixels


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, default=REPO / 'patches/controls/resources/assets/mcheli')
    parser.add_argument('--report', type=Path, default=REPO / '.local/rv-1.1/model-preview/mesh-audit.json')
    parser.add_argument('--skip-rebuild', action='store_true')
    args = parser.parse_args()
    metadata = json.loads((args.assets / 'rv-models.json').read_text(encoding='utf-8'))
    results = {}
    for name, folder in EXPECTED.items():
        model_path = args.assets / 'models' / folder / (name + '.mqo')
        parts = read_mqo(model_path)
        expected_parts = ['$body'] + [f'$blade{i}' for i in range(4 if folder == 'helicopters' else 1)]
        assert list(parts) == expected_parts
        assert hashlib.sha256(model_path.read_bytes()).hexdigest() == metadata[name]['sha256']
        count = 0
        volumes = {}
        duplicate = set()
        for part, (vertices, faces) in parts.items():
            assert all(math.isfinite(value) for point in vertices for value in point)
            volume = 0
            for _, _, triangles in faces:
                for indices in triangles:
                    points = [vertices[index] for index in indices]
                    normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
                    assert dot(normal, normal) > 1e-14, (name, part, indices)
                    key = (part, tuple(sorted(tuple(round(value, 7) for value in point) for point in points)))
                    assert key not in duplicate, (name, part, key)
                    duplicate.add(key)
                    volume += dot(points[0], cross(points[1], points[2])) / 6
                    count += 1
            assert volume > 1e-8, (name, part, volume)
            volumes[part] = volume
            if part.startswith('$blade'):
                pivot = metadata[name]['pivots'][part]
                mean = [sum(p[i] for p in vertices) / len(vertices) for i in range(3)]
                assert max(abs(mean[i] - pivot['position'][i]) for i in range(3)) < 1e-6
                axis = 1 if folder == 'helicopters' else 2
                assert max(p[axis] for p in vertices) - min(p[axis] for p in vertices) < .0201
        assert count == metadata[name]['native_triangle_count'] and count <= 1200
        if folder == 'helicopters':
            vertices, faces = parts['$body']
            lens_faces = [(indices, triangles) for indices, uv, triangles in faces if min(uv[::2]) >= 7 / 8]
            assert lens_faces
            forward_normals = []
            for _, triangles in lens_faces:
                for indices in triangles:
                    points = [vertices[index] for index in indices]
                    normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
                    if abs(normal[2]) > 1e-9:
                        forward_normals.append(normal[2])
            assert forward_normals and min(forward_normals) > 0
        texture_path = args.assets / 'textures' / folder / (name + '.png')
        w, h, texture = read_png(texture_path)
        assert (w, h) == (256, 256) and all(texture[i] == 255 for i in range(3, len(texture), 4))
        assert hashlib.sha256(texture_path.read_bytes()).hexdigest() == metadata[name]['texture_sha256']
        for tile in range(8):
            shades = {texture[(y * w + x) * 4:(y * w + x) * 4 + 3] for y in range(h) for x in range(tile * 32, (tile + 1) * 32)}
            assert len(shades) > 12, (name, tile, len(shades))
        icon_path = args.assets / 'textures/items' / (name + '.png')
        w, h, icon = read_png(icon_path)
        assert (w, h) == (64, 64)
        alpha = icon[3::4]
        visible = sum(bool(value) for value in alpha)
        assert min(alpha) == 0 and max(alpha) == 255 and 200 < visible < 2200
        assert visible == metadata[name]['icon_visible_pixels']
        assert all(alpha[i] == 0 for i in list(range(64)) + list(range(64 * 63, 64 * 64)))
        assert hashlib.sha256(icon_path.read_bytes()).hexdigest() == metadata[name]['icon_sha256']
        results[name] = {'native_triangles': count, 'native_winding_signed_volume_positive': volumes, 'parts': expected_parts, 'duplicate_triangles': 0, 'lens_forward': folder == 'helicopters', 'uv_valid': True, 'finite_vertices': True, 'texture_tiles_detailed': 8, 'icon_visible_pixels': visible}
    if not args.skip_rebuild:
        with tempfile.TemporaryDirectory(prefix='rv-mesh-') as temporary:
            output = Path(temporary) / 'assets'
            subprocess.run([sys.executable, str(REPO / 'tools/build_drone_assets.py'), '--output', str(output)], check=True, stdout=subprocess.DEVNULL)
            for path in output.rglob('*'):
                if path.is_file():
                    relative = path.relative_to(output)
                    assert path.read_bytes() == (args.assets / relative).read_bytes(), str(relative)
    report = {'passed': True, 'native_parser_convention': 'W_MetasequoiaObject parses triangles as V2,V1,V0 and quads as V2,V1,V0 + V0,V3,V2, scales vertices /100', 'renderer_verified': False, 'rebuild_reproducible': not args.skip_rebuild, 'models': results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
