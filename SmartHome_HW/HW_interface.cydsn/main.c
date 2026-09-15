/* ========================================
 *
 * Copyright YOUR COMPANY, THE YEAR
 * All Rights Reserved
 * UNPUBLISHED, LICENSED SOFTWARE.
 *
 * CONFIDENTIAL AND PROPRIETARY INFORMATION
 * WHICH IS THE PROPERTY OF your company.
 *
 * ========================================
*/
#include "project.h"
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>

// NMEA definitions
#define NMEA_MAX_SIZE             82
#define NMEA_START_DELIMITER      '$'
#define NMEA_END_DELIMITER        0x0A
#define NMEA_CHECKSUM_DELIMITER   '*'
#define NMEA_FIELD_DELIMITER      ','
#define NMEA_MSG_NAME_SIZE        4

#define NMEA_SHHWI_CMD          1
#define NMEA_SHHWI_EMPTY        "$SHHWI"

char NMEA_buffer[NMEA_MAX_SIZE];
char NMEA_SHHWI[NMEA_MAX_SIZE] = NMEA_SHHWI_EMPTY;
uint8 NMEA_pointer;
bool NMEA_packet_received = false;
bool NMEA_cmd_received = false;
char cmd_buf[NMEA_MAX_SIZE];

const uint8 fm433_preambula[] = {0, 0, 1, 1, 1, 0};
static const char cmd_test[] = "test";
static const char nmea_shhwi_empty[] = NMEA_SHHWI_EMPTY;

bool NMEA_handle_packet(char *packet, char *NMEA_data);
void NMEA_GetField(char *packet, uint8 field, char *result);

bool check_cmd(const char *cmd);

CY_ISR(isr_server_rx)
{    
    if (NMEA_pointer >= NMEA_MAX_SIZE - 1) NMEA_pointer = 0;
    NMEA_buffer[NMEA_pointer] = UART_Server_GetChar();
    NMEA_buffer[NMEA_pointer + 1] = 0;
    switch(NMEA_buffer[NMEA_pointer])
    {
        case NMEA_START_DELIMITER:
        NMEA_pointer = 1;
        break;
        
        case NMEA_END_DELIMITER:
        if(NMEA_handle_packet(NMEA_buffer, NMEA_SHHWI))
        {
            NMEA_packet_received = true;
        }
        else NMEA_cmd_received = true;
        NMEA_pointer = 0;
        break;
        
        default:
        NMEA_pointer++; 
        break;
    }
}

int main(void)
{
    CyGlobalIntEnable; /* Enable global interrupts. */
    
    UART_FM433_Start();
    UART_Server_Start();
    isr_server_rx_StartEx(isr_server_rx);

    for(;;)
    {
        if(NMEA_packet_received)
        {
            NMEA_packet_received = false;
            UART_FM433_PutArrayConst(fm433_preambula, sizeof(fm433_preambula));
            UART_FM433_PutString(NMEA_buffer);
            UART_Server_PutString("ok");
            UART_Server_PutChar(NMEA_END_DELIMITER);
            NMEA_buffer[0] = 0;
        }
        if(NMEA_cmd_received)
        {
            NMEA_cmd_received = false;
            NMEA_GetField(NMEA_SHHWI, NMEA_SHHWI_CMD, cmd_buf);
            if (check_cmd(cmd_test))
            {
                UART_Server_PutString("ok");
                UART_Server_PutChar(NMEA_END_DELIMITER);
            }
            NMEA_SHHWI[0] = 0;
            strlcat(NMEA_SHHWI, nmea_shhwi_empty, NMEA_MAX_SIZE);
        }
    }
}

bool NMEA_handle_packet(char *packet, char *NMEA_data)
{
    uint8 i, n;
    bool error = false;
    uint8 checksum = 0;
    char *checksum_delimiter;
    char calculated_checksum[3];
        
    // Check if appropriate packet is handled
    if (!strncmp(packet, NMEA_data, NMEA_MSG_NAME_SIZE))
    {
        // Check for receive errors
        for(i = 0; i < NMEA_MAX_SIZE; i++)
        {
            if ((packet[i] < 32) & (packet[i] != 0x0D) & (packet[i] != NMEA_END_DELIMITER)) 
            {
                error = true;
                break;
            }
            if (packet[i] != NMEA_END_DELIMITER) break;
        }
        
        // Validate checksum and cut packet if no receive errors
        if (!error)
        {
            // Find checksum field
            checksum_delimiter = memchr(packet, NMEA_CHECKSUM_DELIMITER, NMEA_MAX_SIZE);
            if (checksum_delimiter == NULL)
                {
                    return true; // Сhecksum delimiter must exist before calculating its position
                }
            i = (uint8)(checksum_delimiter - packet);

            // Reserve two bytes after delimiter for the checksum.
            if (i > NMEA_MAX_SIZE - 3u)
            {
                return true;
            }
            
            // Calculate checksum and compare
            for (n = 1; n < i; n++) checksum ^= (uint8)packet[n];
            sprintf(calculated_checksum, "%02X", (unsigned int)checksum);

            if(strncmp(calculated_checksum, checksum_delimiter + 1, sizeof(calculated_checksum) - 1)) return true;            
            packet[i] = 0; // Cut string to NMEA_CHECKSUM_DELIMITER            
        }   
        
        // Copy buffer to NMEA packet if no errors found
        if (!error) strlcpy(NMEA_data, packet, NMEA_MAX_SIZE);
    }
    else error = true;
    return error;
}

bool check_cmd(const char *cmd)
{
    return !strncmp(cmd_buf, cmd, sizeof(cmd) - 1);
}

void NMEA_GetField(char *packet, uint8 field, char *result)
{
    uint8 i;
    uint8 count = 0;
    
    // Search field
    for (i = 0; (i < NMEA_MAX_SIZE) & (count < field); i++)
    {
        if (packet[i] == NMEA_FIELD_DELIMITER) count++;
    }
    
    // Measure field size
    for (count = 0; count < NMEA_MAX_SIZE; count++)
    {
        if (packet[i + count] == NMEA_FIELD_DELIMITER) break;
        if (packet[i + count] == 0u) break;
    }
    strlcpy(result, packet + i, count + 1);  // Add 1 to count for null terminator
}

/* [] END OF FILE */
