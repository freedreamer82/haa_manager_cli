package main

import (
	"flag"

	"github.com/brutella/hap"
	"github.com/brutella/hap/accessory"

	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {

	version := flag.String("version", "11.9.1", "device fw version")
	model := flag.String("model", "RavenSystem HAA Peregrine", "device fw version")
	sn := flag.String("sn", "112233", "serial number")

	flag.Parse()

	log.Printf("Starting Dev Emulator with version: %s ", *version)
	log.Printf("Pairing Code: 00102003")

	a := accessory.NewSwitch(accessory.Info{
		Name:         "HAA-Emulator-Switch",
		Manufacturer: "José A. Jiménez Campos",
		SerialNumber: *sn,
		Model:        *model,
		Firmware:     *version,
	})

	cs := NewHaaCustomService()
	a.AddS(cs.S)
	s, err := hap.NewServer(hap.NewFsStore("./db"), a.A)
	if err != nil {
		log.Panic(err)
	}

	// Log to console when client (e.g. iOS app) changes the value of the on characteristic
	a.Switch.On.OnValueRemoteUpdate(func(on bool) {
		if on == true {
			log.Println("Client changed switch to on")
		} else {
			log.Println("Client changed switch to off")
		}
	})

	// Periodically toggle the switch's on characteristic
	go func() {
		for {
			on := !a.Switch.On.Value()
			if on == true {
				log.Println("Switch is on")
			} else {
				log.Println("Switch is off")
			}
			a.Switch.On.SetValue(on)
			time.Sleep(20 * time.Second)
		}
	}()

	c := make(chan os.Signal)
	signal.Notify(c, os.Interrupt)
	signal.Notify(c, syscall.SIGTERM)

	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		<-c
		signal.Stop(c)
		cancel()
	}()

	s.ListenAndServe(ctx)
}
