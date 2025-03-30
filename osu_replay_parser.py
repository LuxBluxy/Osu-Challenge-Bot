import lzma
import struct
from datetime import datetime

class OsuReplayAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def parse(self):
        with open(self.file_path, 'rb') as f:
            self.data = {
                'game_mode': ord(f.read(1)),
                'game_version': struct.unpack('<I', f.read(4))[0],
                'beatmap_hash': self._parse_string(f),
                'player_name': self._parse_string(f),
                'replay_hash': self._parse_string(f),
                'count_300': struct.unpack('<H', f.read(2))[0],
                'count_100': struct.unpack('<H', f.read(2))[0],
                'count_50': struct.unpack('<H', f.read(2))[0],
                'gekis': struct.unpack('<H', f.read(2))[0],
                'katus': struct.unpack('<H', f.read(2))[0],
                'misses': struct.unpack('<H', f.read(2))[0],
                'score': struct.unpack('<I', f.read(4))[0],
                'max_combo': struct.unpack('<H', f.read(2))[0],
                'full_combo': ord(f.read(1)),
                'mods': struct.unpack('<I', f.read(4))[0],
                'life_bar': self._parse_string(f),
                'timestamp': datetime.fromtimestamp(struct.unpack('<Q', f.read(8))[0] / 1e9),
                'compressed_length': struct.unpack('<I', f.read(4))[0]
            }

            compressed_data = f.read(self.data['compressed_length'])
            decompressed_data = lzma.decompress(compressed_data, format=lzma.FORMAT_ALONE).decode('utf-8')
            
            self.data['replay_data'] = []
            for frame in decompressed_data.split(','):
                if frame:
                    parts = frame.split('|')
                    if len(parts) >= 4:
                        self.data['replay_data'].append({
                            'time_offset': int(parts[0]),
                            'x': float(parts[1]),
                            'y': float(parts[2]),
                            'keys_pressed': int(parts[3])
                        })
            return self.data

    def _parse_string(self, f):
        length = ord(f.read(1))
        if length == 0:
            return ''
        return f.read(length).decode('utf-8')

    def get_mods(self):
        return self._parse_mods(self.data['mods']) if self.data else None

    @staticmethod
    def _parse_mods(mods):
        mod_list = []
        mod_values = {
            1: 'NF', 2: 'EZ', 4: 'TD', 8: 'HD', 16: 'HR',
            32: 'SD', 64: 'DT', 128: 'RX', 256: 'HT',
            512: 'NC', 1024: 'FL', 2048: 'AU', 4096: 'SO',
            8192: 'AP', 16384: 'PF', 32768: '4K', 65536: '5K',
            131072: '6K', 262144: '7K', 524288: '8K', 1048576: 'FI',
            2097152: 'RD', 4194304: 'CN', 8388608: 'TP',
            16777216: '9K', 33554432: 'CO', 67108864: '1K',
            134217728: '3K', 268435456: '2K', 536870912: 'V2',
            1073741824: 'MR'
        }
        for mod in mod_values:
            if mods & mod:
                mod_list.append(mod_values[mod])
        return ', '.join(mod_list) if mod_list else 'None'

if __name__ == "__main__":
    # Ejemplo 
    analyzer = OsuReplayAnalyzer('tu_replay.osr')
    data = analyzer.parse()
    print(f"Jugador: {data['player_name']}")
    print(f"Mods: {analyzer.get_mods()}")
    print(f"Score: {data['score']}")