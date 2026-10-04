/* Compile the actual application, replacing only hardware APIs. */
#include <assert.h>
#include <setjmp.h>
#include <string.h>
#define main firmware_main
#include "../HW_interface.cydsn/main.c"
#undef main

static uint8 rx_byte;
static jmp_buf main_exit;
static const char *startup_packet;
static const char *interrupt_packet;
static char transmitted[NMEA_MAX_SIZE];
static char server_reply[NMEA_MAX_SIZE];
static unsigned preambles;

size_t strlcpy(char *dst, const char *src, size_t size)
{
    size_t length = strlen(src);
    if (size != 0) {
        size_t copied = length < size - 1u ? length : size - 1u;
        memcpy(dst, src, copied);
        dst[copied] = '\0';
    }
    return length;
}

size_t strlcat(char *dst, const char *src, size_t size)
{
    size_t used = 0;
    while (used < size && dst[used] != '\0') used++;
    if (used == size) return size + strlen(src);
    return used + strlcpy(dst + used, src, size - used);
}

static void feed(const char *data)
{
    while (*data != '\0') {
        rx_byte = (uint8)*data++;
        isr_server_rx();
    }
}

uint8 UART_Server_GetChar(void) { return rx_byte; }
void UART_FM433_Start(void) {}
void UART_Server_Start(void) {}
void isr_server_rx_StartEx(void (*handler)(void))
{
    assert(handler == isr_server_rx);
    feed(startup_packet);
}
void UART_FM433_PutArrayConst(const uint8 *data, size_t size)
{
    assert(size == sizeof(fm433_preambula));
    assert(memcmp(data, fm433_preambula, size) == 0);
    assert(NMEA_packet_received);
    preambles++;
}
void UART_FM433_PutString(const char *data)
{
    size_t index = 0;
    /* Inject an entire next packet while main is reading the TX buffer. */
    while (data[index] != '\0') {
        assert(NMEA_packet_received);
        assert(index < sizeof(transmitted) - 1u);
        transmitted[index] = data[index];
        if (index == 0 && interrupt_packet != NULL) feed(interrupt_packet);
        index++;
    }
    transmitted[index] = '\0';
}
void UART_Server_PutString(const char *data)
{
    strlcat(server_reply, data, sizeof(server_reply));
}
void UART_Server_PutChar(uint8 data)
{
    assert(data == NMEA_END_DELIMITER);
    assert(!NMEA_packet_received);
    strlcat(server_reply, "\n", sizeof(server_reply));
    longjmp(main_exit, 1);
}

static void make_packet(char *packet, const char *body, const char *ending)
{
    unsigned char checksum = 0;
    const char *cursor = body;
    while (*cursor != '\0') checksum ^= (unsigned char)*cursor++;
    int count = snprintf(packet, NMEA_MAX_SIZE, "$%s*%02X%s",
                         body, (unsigned int)checksum, ending);
    assert(count > 0 && count < NMEA_MAX_SIZE);
}

static void valid_checksum(void)
{
    char packet[NMEA_MAX_SIZE];
    make_packet(packet, "SHHWI,test,", "\n");
    assert(!NMEA_handle_packet(packet, NMEA_SHHWI));
    assert(strcmp(NMEA_SHHWI, "$SHHWI,test,") == 0);
    /* Header matching must not depend on mutable output contents. */
    strcpy(NMEA_SHHWI, "different previous output");
    make_packet(packet, "SHHWI,test,", "\r\n");
    assert(!NMEA_handle_packet(packet, NMEA_SHHWI));
}

static void invalid_checksum(void)
{
    char packet[NMEA_MAX_SIZE], original[NMEA_MAX_SIZE];
    make_packet(packet, "SHHWI,test,", "\n");
    char *checksum = strchr(packet, NMEA_CHECKSUM_DELIMITER) + 1u;
    *checksum = *checksum == '0' ? '1' : '0';
    strcpy(original, packet);
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
    assert(strcmp(packet, original) == 0);
    assert(strcmp(NMEA_SHHWI, NMEA_SHHWI_EMPTY) == 0);
}

static void missing_checksum(void)
{
    char packet[NMEA_MAX_SIZE] = "$SHHWI,test,\n";
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
    assert(NMEA_handle_packet(NULL, NMEA_SHHWI));
    assert(NMEA_handle_packet(packet, NULL));
}

static void checksum_at_boundary(void)
{
    char packet[NMEA_MAX_SIZE];
    memset(packet, 'A', sizeof(packet));
    memcpy(packet, "$SHHWI,", sizeof("$SHHWI,") - 1u);
    packet[NMEA_MAX_SIZE - 3u] = NMEA_END_DELIMITER;
    packet[NMEA_MAX_SIZE - 2u] = NMEA_CHECKSUM_DELIMITER;
    packet[NMEA_MAX_SIZE - 1u] = '0';
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
}

static void complete_header(void)
{
    const char *bodies[] = {"SHHXX,test,", "SHHWIextra,test,", "SHHWItest,"};
    char packet[NMEA_MAX_SIZE];
    for (size_t index = 0; index < sizeof(bodies) / sizeof(bodies[0]); index++) {
        make_packet(packet, bodies[index], "\n");
        assert(NMEA_handle_packet(packet, NMEA_SHHWI));
        assert(strcmp(NMEA_SHHWI, NMEA_SHHWI_EMPTY) == 0);
    }
}

static void exact_command(void)
{
    const char *invalid[] = {"", "tes", "testXYZ", "TEST", "test "};
    strcpy(cmd_buf, "test");
    assert(check_cmd(cmd_test));
    assert(!check_cmd(NULL));
    for (size_t index = 0; index < sizeof(invalid) / sizeof(invalid[0]); index++) {
        strcpy(cmd_buf, invalid[index]);
        assert(!check_cmd(cmd_test));
    }
    /* Catch pointer-size comparisons on both 32-bit targets and 64-bit hosts. */
    strcpy(cmd_buf, "command_wrong");
    assert(!check_cmd("command_expected"));
}

static void invalid_characters(void)
{
    char packet[NMEA_MAX_SIZE];
    make_packet(packet, "SHHWI,te\001st,", "\n");
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
    make_packet(packet, "SHHWI,test,", "");
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
    memset(packet, 'A', sizeof(packet));
    memcpy(packet, "$SHHWI,", sizeof("$SHHWI,") - 1u);
    assert(NMEA_handle_packet(packet, NMEA_SHHWI));
}

static void field_extraction(void)
{
    char packet[NMEA_MAX_SIZE] = "$SHHWI,test,,last";
    char field[NMEA_MAX_SIZE];
    NMEA_GetField(packet, NMEA_SHHWI_CMD, field);
    assert(strcmp(field, "test") == 0);
    NMEA_GetField(packet, 2u, field);
    assert(strcmp(field, "") == 0);
    NMEA_GetField(packet, 3u, field);
    assert(strcmp(field, "last") == 0);
    NMEA_GetField(packet, 4u, field);
    assert(field[0] == '\0');
    NMEA_GetField(NULL, 1u, field);
    assert(field[0] == '\0');
    NMEA_GetField(packet, 1u, NULL);
}

static void field_boundaries(void)
{
    char packet[NMEA_MAX_SIZE], field[NMEA_MAX_SIZE];
    memset(packet, 'A', sizeof(packet));
    NMEA_GetField(packet, 1u, field);
    assert(field[0] == '\0');
    packet[0] = NMEA_FIELD_DELIMITER;
    NMEA_GetField(packet, 1u, field);
    assert(field[0] == '\0');
    packet[NMEA_MAX_SIZE - 1u] = '\0';
    NMEA_GetField(packet, 1u, field);
    assert(strlen(field) == NMEA_MAX_SIZE - 2u);
}

static void rx_overflow(void)
{
    for (size_t index = 0; index < NMEA_MAX_SIZE * 3u; index++) {
        rx_byte = 'A';
        isr_server_rx();
        assert(NMEA_pointer < NMEA_MAX_SIZE);
        assert(NMEA_buffer[NMEA_pointer] == '\0');
    }
    assert(!NMEA_packet_received && !NMEA_cmd_received);
}

static void resynchronize(void)
{
    char packet[NMEA_MAX_SIZE];
    feed("garbage$unfinished");
    make_packet(packet, "SHHWI,test,", "\n");
    feed(packet);
    assert(NMEA_cmd_received && !NMEA_packet_received);
    assert(strcmp(NMEA_SHHWI, "$SHHWI,test,") == 0);
}

static void pending_output(void)
{
    char packet[NMEA_MAX_SIZE], first[NMEA_MAX_SIZE];
    make_packet(first, "SHFTL,ALARM,1,", "\n");
    feed(first);
    assert(NMEA_packet_received);
    assert(strcmp(NMEA_output, first) == 0);
    make_packet(packet, "SHBCC,OFF,", "\n");
    feed(packet);
    assert(strcmp(NMEA_output, first) == 0);
    make_packet(packet, "SHHWI,test,", "\n");
    feed(packet);
    assert(NMEA_cmd_received);
    assert(strcmp(NMEA_output, first) == 0);
}

static void transmit_interleaving(void)
{
    char first[NMEA_MAX_SIZE], second[NMEA_MAX_SIZE];
    make_packet(first, "SHBCC,ON,", "\n");
    make_packet(second, "SHBCC,OFF,", "\n");
    startup_packet = first;
    interrupt_packet = second;
    if (setjmp(main_exit) == 0) firmware_main();
    assert(strcmp(transmitted, first) == 0);
    assert(strcmp(server_reply, "ok\n") == 0);
    assert(preambles == 1u);
    assert(!NMEA_packet_received);
    feed(second);
    assert(NMEA_packet_received);
    assert(strcmp(NMEA_output, second) == 0);
}

static void handshake_main(void)
{
    char packet[NMEA_MAX_SIZE];
    make_packet(packet, "SHHWI,test,", "\n");
    startup_packet = packet;
    if (setjmp(main_exit) == 0) firmware_main();
    assert(strcmp(server_reply, "ok\n") == 0);
    assert(preambles == 0);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
#define RUN(name) if (strcmp(argv[1], #name) == 0) { name(); return 0; }
    RUN(valid_checksum)
    RUN(invalid_checksum)
    RUN(missing_checksum)
    RUN(checksum_at_boundary)
    RUN(complete_header)
    RUN(exact_command)
    RUN(invalid_characters)
    RUN(field_extraction)
    RUN(field_boundaries)
    RUN(rx_overflow)
    RUN(resynchronize)
    RUN(pending_output)
    RUN(transmit_interleaving)
    RUN(handshake_main)
    return 2;
}
