<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>dtm</Name>
    <UserStyle>
      <Name>dtm_style</Name>
      <Title>Digital Terrain Model - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <!-- 0 = NoData transparent -->
              <ColorMapEntry color="#000000" quantity="0"   opacity="0" label="NoData"/>
              <ColorMapEntry color="#1a1a1a" quantity="1"   opacity="1"/>
              <ColorMapEntry color="#2b2b2b" quantity="10"  opacity="1"/>
              <ColorMapEntry color="#3c3c3c" quantity="20"  opacity="1"/>
              <ColorMapEntry color="#4d4d4d" quantity="30"  opacity="1"/>
              <ColorMapEntry color="#5e5e5e" quantity="50"  opacity="1"/>
              <ColorMapEntry color="#6f6f6f" quantity="70"  opacity="1"/>
              <ColorMapEntry color="#808080" quantity="90"  opacity="1"/>
              <ColorMapEntry color="#919191" quantity="110" opacity="1"/>
              <ColorMapEntry color="#a2a2a2" quantity="130" opacity="1"/>
              <ColorMapEntry color="#b3b3b3" quantity="150" opacity="1"/>
              <ColorMapEntry color="#c4c4c4" quantity="170" opacity="1"/>
              <ColorMapEntry color="#d5d5d5" quantity="190" opacity="1"/>
              <ColorMapEntry color="#e6e6e6" quantity="220" opacity="1"/>
              <ColorMapEntry color="#ffffff" quantity="254" opacity="1"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
