int main(void) {
    int a = 0xFF;    /* 255 */
    int b = 0x0F;    /* 15  */
    int band = a & b;
    int bor  = a | b;
    int bxor = a ^ b;
    int bshl = a << 2;
    int bshr = a >> 2;
    return band + bor + bxor + bshl + bshr;
}
