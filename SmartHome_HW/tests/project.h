#ifndef HOST_TEST_PROJECT_H
#define HOST_TEST_PROJECT_H
#include <stddef.h>
#include <stdint.h>

typedef uint8_t uint8;
#define CY_ISR(name) void name(void)
#define CyGlobalIntEnable ((void)0)

uint8 UART_Server_GetChar(void);
void UART_FM433_Start(void);
void UART_Server_Start(void);
void isr_server_rx_StartEx(void (*handler)(void));
void UART_FM433_PutArrayConst(const uint8 *data, size_t size);
void UART_FM433_PutString(const char *data);
void UART_Server_PutString(const char *data);
void UART_Server_PutChar(uint8 data);
size_t strlcpy(char *dst, const char *src, size_t size);
size_t strlcat(char *dst, const char *src, size_t size);
#endif
