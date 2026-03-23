<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>dsm</Name>
    <UserStyle>
      <Name>dsm_style</Name>
      <Title>Digital Surface Model - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <ColorMapEntry color="#1a1a2e" quantity="0"   opacity="1" label="Low"/>
              <ColorMapEntry color="#2d4a3e" quantity="17"  opacity="1"/>
              <ColorMapEntry color="#4a7c59" quantity="35"  opacity="1"/>
              <ColorMapEntry color="#8fb339" quantity="58"  opacity="1"/>
              <ColorMapEntry color="#d4c957" quantity="87"  opacity="1"/>
              <ColorMapEntry color="#e8a84c" quantity="115" opacity="1"/>
              <ColorMapEntry color="#d45b3a" quantity="150" opacity="1"/>
              <ColorMapEntry color="#a83279" quantity="196" opacity="1"/>
              <ColorMapEntry color="#ffffff" quantity="254" opacity="1" label="High"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
