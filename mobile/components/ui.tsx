import React from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, ui } from "@/lib/theme";
export function Page({title,subtitle,children,refreshing,onRefresh}:{title:string;subtitle?:string;children:React.ReactNode;refreshing?:boolean;onRefresh?:()=>void}){return <SafeAreaView style={ui.screen} edges={["top"]}><ScrollView contentContainerStyle={ui.content} refreshControl={onRefresh?<RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.brand}/>:undefined}><View style={{gap:6}}><Text style={ui.title}>{title}</Text>{subtitle&&<Text style={ui.subtitle}>{subtitle}</Text>}</View>{children}</ScrollView></SafeAreaView>;}
export function Card({children}:{children:React.ReactNode}){return <View style={ui.card}>{children}</View>;}
export function Action({label,onPress,secondary,disabled}:{label:string;onPress:()=>void;secondary?:boolean;disabled?:boolean}){return <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityState={{disabled}} style={({pressed})=>[secondary?ui.secondaryButton:ui.button,{opacity:disabled?0.55:pressed?0.82:1}]}><Text style={secondary?ui.secondaryText:ui.buttonText}>{label}</Text></Pressable>;}
export function Loading(){return <View style={{padding:22,alignItems:"center"}}><ActivityIndicator size="large" color={colors.brand}/><Text style={[ui.small,{marginTop:8}]}>Loading your information…</Text></View>;}
export function Notice({children,warning}:{children:string;warning?:boolean}){return <View accessibilityRole="alert" style={[ui.card,{backgroundColor:warning?"#fbefef":"#eaf3f6",borderColor:warning?"#e8c4c7":"#cfdee6"}]}><Text style={[ui.small,{color:warning?colors.high:colors.info}]}>{children}</Text></View>;}
export function dateLabel(value:string){return new Intl.DateTimeFormat(undefined,{dateStyle:"medium"}).format(new Date(value));}
