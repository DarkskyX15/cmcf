int main(void) {
    char  a = 100;
    short b = 200;
    int   c = a;
    int   d = b;
    char  e = (char)d;
    int   f = (int)e;
    return c + d + e + f;
}
