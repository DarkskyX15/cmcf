int ternary(int a, int b) {
    return (a > b) ? a : b;
}

int arr[4] = {10, 20, 30, 40};

int array_read(void) {
    return arr[2];
}

int main(void) {
    int t = ternary(15, 25);
    int v = array_read();
    return t + v;
}
