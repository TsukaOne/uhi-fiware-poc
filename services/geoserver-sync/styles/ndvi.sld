<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>ndvi</Name>
    <UserStyle>
      <Name>ndvi_style</Name>
      <Title>Normalized Difference Vegetation Index - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap>
              <ColorMapEntry color="#d7191c" quantity="0"   opacity="1" label="No vegetation"/>
              <ColorMapEntry color="#d53b22" quantity="33"  opacity="1"/>
              <ColorMapEntry color="#d35d28" quantity="66"  opacity="1"/>
              <ColorMapEntry color="#d17f2e" quantity="99"  opacity="1"/>
              <ColorMapEntry color="#ebc781" quantity="132" opacity="1"/>
              <ColorMapEntry color="#d2f79f" quantity="165" opacity="1"/>
              <ColorMapEntry color="#3ed537" quantity="198" opacity="1"/>
              <ColorMapEntry color="#2ab33d" quantity="229" opacity="1"/>
              <ColorMapEntry color="#1a9641" quantity="254" opacity="1" label="High vegetation"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
