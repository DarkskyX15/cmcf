int sum_to(int n) {
    int result = 0;
    int i = 0;
    while (i < n) {
        result = result + i;
        i = i + 1;
    }
    return result;
}

int main(void) {
    int s = sum_to(5);
    return s;
}
