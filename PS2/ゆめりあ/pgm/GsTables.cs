using System;

// GS page/block/column addressing. The PGM payload is uploaded as PSMCT32
// words, then sampled as the texture's declared PSM.
static class GsTables
{
    public const int UploadBw = 16;
    public static readonly int[] ClutT32I8 = { 0,1,4,5,8,9,12,13,2,3,6,7,10,11,14,15,64,65,68,69,72,73,76,77,66,67,70,71,74,75,78,79,16,17,20,21,24,25,28,29,18,19,22,23,26,27,30,31,80,81,84,85,88,89,92,93,82,83,86,87,90,91,94,95,32,33,36,37,40,41,44,45,34,35,38,39,42,43,46,47,96,97,100,101,104,105,108,109,98,99,102,103,106,107,110,111,48,49,52,53,56,57,60,61,50,51,54,55,58,59,62,63,112,113,116,117,120,121,124,125,114,115,118,119,122,123,126,127 };
    public static readonly int[] ClutT32I4 = { 0, 1, 4, 5, 8, 9, 12, 13, 2, 3, 6, 7, 10, 11, 14, 15 };
    public static int ClutAddress(int logical) => (ClutT32I8[logical & 0x70] | (logical & 0x80)) + ClutT32I4[logical & 15];
    public static readonly int[] Clut8Block = { 24, 25, 0, 2, 26, 27, 4, 6, 28, 29, 8, 10, 30, 31, 12, 14, 1, 3, 16, 17, 5, 7, 18, 19, 9, 11, 20, 21, 13, 15, 22, 23 };

    static readonly int[,] Block32 = { {0,1,4,5,16,17,20,21}, {2,3,6,7,18,19,22,23}, {8,9,12,13,24,25,28,29}, {10,11,14,15,26,27,30,31} };
    static readonly int[,] C32 = Table("0 1 4 5 8 9 12 13;2 3 6 7 10 11 14 15;16 17 20 21 24 25 28 29;18 19 22 23 26 27 30 31;32 33 36 37 40 41 44 45;34 35 38 39 42 43 46 47;48 49 52 53 56 57 60 61;50 51 54 55 58 59 62 63");
    static readonly int[,] C8 = Table(@"0 4 16 20 32 36 48 52 2 6 18 22 34 38 50 54;8 12 24 28 40 44 56 60 10 14 26 30 42 46 58 62;33 37 49 53 1 5 17 21 35 39 51 55 3 7 19 23;41 45 57 61 9 13 25 29 43 47 59 63 11 15 27 31;96 100 112 116 64 68 80 84 98 102 114 118 66 70 82 86;104 108 120 124 72 76 88 92 106 110 122 126 74 78 90 94;65 69 81 85 97 101 113 117 67 71 83 87 99 103 115 119;73 77 89 93 105 109 121 125 75 79 91 95 107 111 123 127;128 132 144 148 160 164 176 180 130 134 146 150 162 166 178 182;136 140 152 156 168 172 184 188 138 142 154 158 170 174 186 190;161 165 177 181 129 133 145 149 163 167 179 183 131 135 147 151;169 173 185 189 137 141 153 157 171 175 187 191 139 143 155 159;224 228 240 244 192 196 208 212 226 230 242 246 194 198 210 214;232 236 248 252 200 204 216 220 234 238 250 254 202 206 218 222;193 197 209 213 225 229 241 245 195 199 211 215 227 231 243 247;201 205 217 221 233 237 249 253 203 207 219 223 235 239 251 255");

    static int[,] Table(string s) { var rows = s.Split(';').Select(x => x.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(int.Parse).ToArray()).ToArray(); var a = new int[rows.Length, rows[0].Length]; for (var y = 0; y < rows.Length; y++) for (var x = 0; x < rows[y].Length; x++) a[y, x] = rows[y][x]; return a; }

    public static int Addr(int x, int y, int bw, int psm)
    {
        int pw, ph, blockW, unit, blockH; int[,] columns, blocks;
        if (psm == 0) { pw = 64; ph = 32; blockW = 8; unit = 2048; blockH = 8; columns = C32; blocks = Block32; }
        else if (psm == 19) { pw = 128; ph = 64; blockW = 16; unit = 8192; blockH = 16; columns = C8; blocks = Block32; }
        else throw new InvalidDataException("unsupported PSM " + psm);
        var pages = Math.Max(1, bw / (pw / 64)); var sx = x % pw; var sy = y % ph;
        return ((y / ph) * pages + x / pw) * unit + blocks[sy / blockH, sx / blockW] * (unit / 32) + columns[sy % columns.GetLength(0), sx % blockW];
    }
}
