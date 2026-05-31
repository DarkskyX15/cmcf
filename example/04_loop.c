float sum_to(float n) {
    float result = 1.0f;
    float i = 1.0f;
    while (i < n) {
        result = result * i;
        i = i + 1.0f;
    }
    return result;
}

int main(void) {
    float s = sum_to(5);
    return (int)s;
}
