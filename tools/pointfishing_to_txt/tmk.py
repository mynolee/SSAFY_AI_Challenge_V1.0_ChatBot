import math

A = 6378137.0
F = 1.0 / 298.257222101
K0 = 0.9996
LON0 = math.radians(127.5)
LAT0 = math.radians(38.0)
X0, Y0 = 1000000.0, 2000000.0
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)


def _m(phi):
    return A * ((1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256) * phi
                - (3 * E2 / 8 + 3 * E2**2 / 32 + 45 * E2**3 / 1024) * math.sin(2 * phi)
                + (15 * E2**2 / 256 + 45 * E2**3 / 1024) * math.sin(4 * phi)
                - (35 * E2**3 / 3072) * math.sin(6 * phi))


def utmk_to_wgs84(x, y):
    """EPSG:5179 (Korea 2000 / Unified CS) -> WGS84 lat, lon."""
    m = _m(LAT0) + (y - Y0) / K0
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    mu = m / (A * (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256))
    phi1 = (mu
            + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
            + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
            + (151 * e1**3 / 96) * math.sin(6 * mu)
            + (1097 * e1**4 / 512) * math.sin(8 * mu))
    c1 = EP2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - X0) / (n1 * K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * EP2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * EP2 - 3 * c1**2) * d**6 / 720)
    lon = LON0 + (d
                  - (1 + 2 * t1 + c1) * d**3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * EP2 + 24 * t1**2) * d**5 / 120) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)
