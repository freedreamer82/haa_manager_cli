package main

import (
	"fmt"

	"github.com/brutella/hap/characteristic"
	service "github.com/brutella/hap/service"
)

const HAA_CUSTOM_SERVICE = "F0000100-0218-2017-81BF-AF2B7C833922"
const HAA_CUSTOM_CONFIG_CHAR = "F0000101-0218-2017-81BF-AF2B7C833922"

type HaaCustomService struct {
	*service.S
	ValueString *characteristic.String
}

func newCharUUID(value string) *characteristic.String {
	uuid := characteristic.NewString(value)
	uuid.Permissions = []string{characteristic.PermissionRead,
		characteristic.PermissionHidden, characteristic.PermissionWrite}
	uuid.Description = "ID"
	uuid.SetValue("")
	return uuid
}

func NewHaaCustomService() *HaaCustomService {
	s := HaaCustomService{}
	s.S = &service.S{}
	s.Hidden = true
	s.Primary = false
	s.Type = HAA_CUSTOM_SERVICE

	s.ValueString = newCharUUID(HAA_CUSTOM_CONFIG_CHAR)
	s.AddC(s.ValueString.C)

	s.ValueString.OnValueRemoteUpdate(func(value string) {
		fmt.Printf("HAA Custom Value: %s\r\n", value)
	})

	return &s
}
